import argparse
import subprocess
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import config
from .core.orchestrator import Orchestrator

HISTORY_FILE = Path.home() / ".cozmo" / ".history"


class FileCompleter(Completer):
    """Fuzzy file completer triggered by @ prefix."""
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self._files: list[str] | None = None

    def _get_files(self) -> list[str]:
        if self._files is None:
            self._files = []
            for f in sorted(self.cwd.rglob("*")):
                if f.is_file() and ".git" not in f.parts:
                    self._files.append(str(f.relative_to(self.cwd)))
        return self._files

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if "@" not in text:
            return
        idx = text.rindex("@")
        partial = text[idx + 1:]
        partial_lower = partial.lower()
        count = 0
        for f in self._get_files():
            if partial_lower in f.lower():
                yield Completion("@" + f, start_position=-(len(partial) + 1))
                count += 1
                if count >= 20:
                    return


def _safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


def _status_bar(registry) -> str:
    agent = registry.current
    n = len([m for m in agent.history if m[0] == "user"]) if hasattr(agent, "history") else 0
    name = registry.current_name
    return f"[{name} turns:{n}]"


def _handle_slash(cmd: str) -> tuple[str, bool]:
    cmd = cmd.strip().lower()
    if cmd in ("exit", "quit", "q"):
        return "", True
    return cmd, False


def interactive_session(cfg: dict, initial_query: str | None = None):
    orch = Orchestrator(cfg)
    if initial_query:
        _safe_print(f"\nCozmo: {orch.run(initial_query)}\n")
    while True:
        try:
            user = input("\nYou: ")
            if user.lower() in ("exit", "quit"):
                break
            result = orch.run(user)
            _safe_print(f"Cozmo: {result}")
        except (EOFError, KeyboardInterrupt):
            break


def coding_session(cfg: dict, project_path: Path, query: str | None = None, auto: bool = False):
    from .core.agent_registry import AgentRegistry

    registry = AgentRegistry(project_path, cfg, auto=auto)

    if query:
        _safe_print(f"\nCozmo: {registry.current.run(query)}\n")
        return

    HistoryFile = HISTORY_FILE
    HistoryFile.parent.mkdir(parents=True, exist_ok=True)

    kb = KeyBindings()

    @kb.add("f2")
    def _(event):
        registry.switch(1)
        print(f"\n → switched to {registry.current_name}")
        status = _status_bar(registry)
        event.app.current_buffer.text = ""
        event.app.invalidate()

    session = PromptSession(
        history=FileHistory(str(HistoryFile)),
        completer=FileCompleter(project_path),
        complete_while_typing=True,
        key_bindings=kb,
    )

    print(f"Session in {project_path}. /help for commands, F2 to switch agents.")
    while True:
        try:
            status = _status_bar(registry)
            line = session.prompt(f"\n{status}\nYou: ")
        except (EOFError, KeyboardInterrupt):
            break

        # !cmd shell passthrough
        if line.startswith("!"):
            cmd = line[1:].strip()
            _safe_print(f"$ {cmd}")
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                out = r.stdout or r.stderr or "(no output)"
                _safe_print(out)
            except Exception as e:
                _safe_print(f"Error: {e}")
            continue

        # / slash commands
        if line.startswith("/"):
            cmd_raw, should_exit = _handle_slash(line[1:])
            if should_exit:
                break
            cmd = cmd_raw
            if cmd in ("new", "clear"):
                registry.switch(0)
                registry = AgentRegistry(project_path, cfg)
                print("Session cleared.")
            elif cmd == "agent":
                print(f"Current agent: {registry.current_name}")
            elif cmd == "agents":
                for name, idx in registry.list():
                    mark = " ←" if idx == registry._current else ""
                    print(f"  {idx + 1}. {name}{mark}")
            elif cmd == "help":
                print(
                    "Commands:\n"
                    "  /help           Show this help\n"
                    "  /new            Clear session\n"
                    "  /exit           Quit\n"
                    "  /compact        Summarize & compact context\n"
                    "  /agent          Show current agent\n"
                    "  /agents         List all agents\n"
                    "  @file           Attach file to context\n"
                    "  !command        Run shell command\n"
                    "  F2              Switch agent"
                )
            elif cmd == "compact":
                registry.current.compact()
                print("Context compacted.")
            else:
                print(f"Unknown: /{cmd}")
            continue

        if not line.strip():
            continue

        result = registry.current.run(line)
        _safe_print(f"Cozmo: {result}")


def run_telegram(cfg: dict):
    from .telegram_bot import TelegramBot
    from .tools.telegram import set_bot_instance

    token = cfg.get("telegram", {}).get("bot_token", "")
    if not token:
        print("Error: telegram.bot_token not set in config")
        return

    orch = Orchestrator(cfg)
    bot = TelegramBot(token, orch)
    set_bot_instance(bot)
    print("Cozmo Telegram bot started. Press Ctrl+C to stop.")
    bot.run()


def main():
    parser = argparse.ArgumentParser("cozmo")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Generate ~/.cozmo/config.toml")
    sub.add_parser("telegram", help="Run Cozmo as Telegram bot")

    run_parser = sub.add_parser("run", help="Run a query or start interactive")
    run_parser.add_argument("query", nargs="?", help="Single query (omit for interactive)")

    code_parser = sub.add_parser("code", help="Start a coding session")
    code_parser.add_argument("query", nargs="?", help="Single query (omit for interactive)")
    code_parser.add_argument("--path", default=".", help="Project directory")
    code_parser.add_argument("--init", action="store_true", help="Index project into Chroma")
    code_parser.add_argument("--auto", action="store_true", help="Non-interactive — allow all permission prompts")

    sub.add_parser("tui", help="Launch the Textual TUI")

    config_parser = sub.add_parser("config", help="Manage configuration")
    config_parser.add_argument("action", choices=["show", "set", "reset"], nargs="?")
    config_parser.add_argument("key", nargs="?", help="Config key (e.g. models.coder)")
    config_parser.add_argument("value", nargs="?", help="Config value")

    args = parser.parse_args()

    if args.command == "init":
        cfg = config.init()
        print(f"Config created at {config.CONFIG_PATH}")

    elif args.command == "telegram":
        cfg = config.load()
        run_telegram(cfg)

    elif args.command == "run":
        cfg = config.load()
        interactive_session(cfg, args.query)

    elif args.command == "code":
        from .code_indexer import ProjectIndex

        cfg = config.load()
        project_path = Path(args.path).resolve()
        if args.init:
            idx = ProjectIndex(project_path)
            n = idx.index_all()
            print(f"Indexed {n} files in {project_path}")
            return
        coding_session(cfg, project_path, args.query, auto=args.auto)

    elif args.command == "tui":
        from .tui.app import CozmoApp
        CozmoApp().run()

    elif args.command == "config":
        from .config_cli import handle_config
        handle_config(args, config)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
