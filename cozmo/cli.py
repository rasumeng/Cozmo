import argparse
from . import config

def interactive_session(cfg: dict, initial_query: str | None = None):
    """Placeholder — runs agent loop (Phase 1)."""
    if initial_query:
        print(f"Query: {initial_query}")
    else:
        print("Interactive mode started (not yet implemented)")

def main():
    parser = argparse.ArgumentParser("cozmo")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Generate ~/.cozmo/config.toml")
    run_parser = sub.add_parser("run", help="Run a query or start interactive")
    run_parser.add_argument("query", nargs="?", help="Single query (omit for interactive)")

    args = parser.parse_args()
    if args.command == "init":
        cfg = config.init()
        print(f"Config created at {config.CONFIG_PATH}")
    elif args.command == "run":
        cfg = config.load()
        interactive_session(cfg, args.query)

if __name__ == "__main__":
    main()
