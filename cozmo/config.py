from pathlib import Path
import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".cozmo"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "models": {
        "fast": "phi4-mini:3.8b",
        "balanced": "qwen3:8b",
        "heavy": "qwen2.5-coder:14b",
        "classifier": "qwen3:0.6b",
    },
    "ollama": {"url": "http://localhost:11434"},
    "memory": {"max_turns_before_summary": 5, "max_short_term_pairs": 10},
    "desktop": {"enabled": False},
    "telegram": {"enabled": False, "bot_token": "", "allowed_chat_ids": []},
}

def load() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    return DEFAULT_CONFIG

def init() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "wb") as f:
            tomli_w.dump(DEFAULT_CONFIG, f)
    return load()
