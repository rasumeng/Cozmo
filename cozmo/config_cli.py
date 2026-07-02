"""cozmo config show|set|reset"""


def _deep_get(d: dict, key: str):
    parts = key.split(".")
    for p in parts:
        if isinstance(d, dict) and p in d:
            d = d[p]
        else:
            return None
    return d


def _deep_set(d: dict, key: str, value):
    parts = key.split(".")
    for p in parts[:-1]:
        if p not in d:
            d[p] = {}
        d = d[p]
    d[parts[-1]] = value


def _print_cfg(d: dict, indent: str = ""):
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{indent}{k}:")
            _print_cfg(v, indent + "  ")
        else:
            print(f"{indent}{k} = {v!r}")


def handle_config(args, config_mod):
    cfg = config_mod.load()

    if args.action is None or args.action == "show":
        _print_cfg(cfg)

    elif args.action == "reset":
        cfg = config_mod.init()
        print("Config reset to defaults.")

    elif args.action == "set":
        if not args.key or args.value is None:
            print("Usage: cozmo config set <key> <value>")
            return
        try:
            parsed = int(args.value)
        except ValueError:
            try:
                parsed = float(args.value)
            except ValueError:
                parsed = args.value
        _deep_set(cfg, args.key, parsed)
        import tomli_w
        with open(config_mod.CONFIG_PATH, "wb") as f:
            tomli_w.dump(cfg, f)
        print(f"Set {args.key} = {parsed!r}")
