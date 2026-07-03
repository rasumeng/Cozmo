from pathlib import Path
import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".cozmo"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "models": {
        "classifier": "phi4-mini:3.8b",
        "chat": "qwen2.5:7b",
        "coder": "ornith:9b",
        "vision": "qwen2.5vl:7b",
        "research": "qwen3:8b",
    },
    "ollama": {"url": "http://localhost:11434"},
    "memory": {"max_turns_before_summary": 5, "max_short_term_pairs": 10},
    "runtime": {
        "max_history": 10,
        "max_steps": 8,
        "max_tool_output_chars": 8000,
        "memory_distance_threshold": 0.5,
        "max_memory_results": 3,
        "max_project_results": 3,
        "temperatures": {"chat": 0.6, "work": 0.0, "research": 0.2},
        "tool_gate": {
            "chat": [],
            "research": ["web_search", "web_search_pipeline", "web_fetch", "calculator"],
            # "work": omitted => all registered tools
        },
    },
    "agents": {
        "primary": ["build", "plan"],
        "build": {"model": None, "permissions": {}},
        "plan": {"model": None, "permissions": {"write_file": "deny", "edit_file": "deny", "run_command": "deny"}},
    },
    "permissions": {
        "write_file": "ask",
        "edit_file": "ask",
        "run_command": {"*": "ask", "git *": "allow", "dir *": "allow"},
    },
    "code": {"index_extensions": ["*"]},
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
