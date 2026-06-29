from . import register_tool
from datetime import datetime
from pathlib import Path
import pyperclip
from PIL import ImageGrab

SCREENSHOT_DIR = Path.home() / ".cozmo" / "screenshots"


@register_tool()
def screenshot() -> str:
    """Take a screenshot and save to disk. Returns file path."""
    if not _is_desktop_enabled():
        return "Error: desktop tools disabled in config"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    img = ImageGrab.grab()
    img.save(path)
    return str(path)


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