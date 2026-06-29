import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import config
from .core.orchestrator import Orchestrator


def _safe_print(text: str):
    """Print text, stripping unsupported characters on Windows console."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


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


if __name__ == "__main__":
    main()
