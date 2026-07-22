import base64
import json
from datetime import datetime
from pathlib import Path
import pyperclip
from PIL import ImageGrab
import requests

from . import register_tool

SCREENSHOT_DIR = Path.home() / ".cozmo" / "screenshots"
OLLAMA_URL = "http://localhost:11434"


def _get_vision_model() -> str:
    from .. import config
    from ..ollama_util import get_ollama_models, pick_model
    cfg = config.load()
    model = cfg.get("models", {}).get("vision")
    if model:
        return model
    ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    installed = get_ollama_models(ollama_url)
    return pick_model(installed, "vision")


def _analyze_image(image_path: str, prompt: str = "Describe this image in detail.") -> str:
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        model = _get_vision_model()
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                "stream": False,
            },
        )
        data = resp.json()
        return data.get("message", {}).get("content", "No description returned.")
    except Exception as e:
        return f"Error analyzing image: {e}"


@register_tool()
def screenshot(prompt: str = "Describe what's on this screen.") -> str:
    """Take a screenshot and analyze it. Optional: custom prompt for what to look for."""
    if not _is_desktop_enabled():
        return "Error: desktop tools disabled in config"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    img = ImageGrab.grab()
    img.save(path)
    return _analyze_image(str(path), prompt)


@register_tool()
def analyze_image(file_path: str, prompt: str = "Describe this image in detail.") -> str:
    """Analyze an existing image file. Provide file path and optional prompt."""
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"
    return _analyze_image(file_path, prompt)


@register_tool()
def clipboard_read() -> str:
    """Read text from clipboard."""
    if not _is_desktop_enabled():
        return "Error: desktop tools disabled in config"
    try:
        return pyperclip.paste()
    except Exception as e:
        return f"Error reading clipboard: {e}"


def _is_desktop_enabled() -> bool:
    from .. import config
    cfg = config.load()
    return cfg.get("desktop", {}).get("enabled", False)
