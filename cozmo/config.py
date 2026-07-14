import copy
import os
from pathlib import Path
import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".cozmo"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "models": {
        "classifier": "openbmb/minicpm5:Q4_K_M",
        "router": "openbmb/minicpm5:Q4_K_M",
        "orchestrator": "openbmb/minicpm5:Q4_K_M",
        "chat": "qwen3:8b",
        "agent": "qwen3:8b",
        "coder": "ornith:9b",
        "vision": "qwen2.5vl:7b",
        "research": "qwen3:8b",
        "max_tokens": 2048,
    },
    "ollama": {"url": "http://localhost:11434"},
    "memory": {"max_turns_before_summary": 5, "max_short_term_pairs": 10},
    "router": {
        "use_llm": False,
    },
    "workspace": {
        "path": "./workspace",
        "knowledge": "./knowledge",
        "git_repo": "",
    },
    "personality": "",
    "search": {
        "url": "http://localhost:8080",
        "backend": "searxng",
    },
    "mcp": {
        "servers": {},
    },
    "runtime": {
        "lightweight_mode": False,
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

def _resolve_paths(cfg: dict) -> dict:
    workspace = cfg.get("workspace")
    if isinstance(workspace, dict):
        for key in ("path", "knowledge"):
            value = workspace.get(key)
            if value:
                workspace[key] = str(Path(value).expanduser().resolve())
    return cfg

def _apply_env_overrides(cfg: dict) -> dict:
    telegram = cfg.get("telegram")
    if isinstance(telegram, dict):
        env_token = os.getenv("COZMO_TELEGRAM_BOT_TOKEN")
        if telegram.get("bot_token"):
            print("Warning: telegram.bot_token found in config file; prefer the COZMO_TELEGRAM_BOT_TOKEN env var.")
        if env_token:
            telegram["bot_token"] = env_token
    return cfg

def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                cfg = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError) as e:
            print(f"Warning: failed to parse config file {CONFIG_PATH}: {e}. Using defaults.")
            cfg = copy.deepcopy(DEFAULT_CONFIG)
    else:
        cfg = copy.deepcopy(DEFAULT_CONFIG)
    return _resolve_paths(_apply_env_overrides(cfg))

def init() -> dict:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            with open(CONFIG_PATH, "wb") as f:
                tomli_w.dump(DEFAULT_CONFIG, f)
    except (PermissionError, OSError) as e:
        print(f"Warning: could not create config at {CONFIG_PATH}: {e}. Using defaults.")
    return load()
