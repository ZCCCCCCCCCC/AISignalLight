from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

MARKER = "ai-traffic-light-win"
PLACEHOLDER = "__HOOK_CMD__"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".broken")
        path.replace(backup)
        return deepcopy(default)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def replace_placeholder(value: Any, hook_command: str) -> Any:
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, hook_command)
    if isinstance(value, list):
        return [replace_placeholder(item, hook_command) for item in value]
    if isinstance(value, dict):
        return {key: replace_placeholder(item, hook_command) for key, item in value.items()}
    return value


def shell_quote_command_path(command: str) -> str:
    if command.startswith('"') or command.startswith("'"):
        return command
    if " " not in command and "\t" not in command:
        return command
    return f'"{command}"'


def strip_managed(entries: list[Any]) -> list[Any]:
    return [entry for entry in entries if MARKER not in json.dumps(entry)]


def merge_nested(config_path: Path, fragment: dict[str, Any]) -> None:
    config = load_json(config_path, {})
    if not isinstance(config, dict):
        config = {}
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        config["hooks"] = hooks

    for event, incoming in fragment.items():
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            existing = []
        hooks[event] = strip_managed(existing) + deepcopy(incoming)

    write_json(config_path, config)


def merge_cursor(config_path: Path, fragment: dict[str, Any]) -> None:
    config = load_json(config_path, {"version": 1, "hooks": {}})
    if not isinstance(config, dict):
        config = {"version": 1, "hooks": {}}
    config.setdefault("version", 1)

    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        config["hooks"] = hooks

    for event in list(hooks.keys()):
        entries = hooks.get(event)
        if event in fragment or not isinstance(entries, list):
            continue
        if entries and all(MARKER in json.dumps(entry) for entry in entries):
            del hooks[event]

    for event, incoming in fragment.items():
        hooks[event] = deepcopy(incoming)

    write_json(config_path, config)


def merge_antigravity(config_path: Path, fragment: dict[str, Any]) -> None:
    config = load_json(config_path, {})
    if not isinstance(config, dict):
        config = {}

    for key in list(config.keys()):
        if MARKER in key:
            del config[key]

    for key, value in fragment.items():
        config[key] = deepcopy(value)

    write_json(config_path, config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hook-merge")
    parser.add_argument("target", choices=["antigravity", "claude", "codex", "cursor"])
    parser.add_argument("config_path")
    parser.add_argument("fragment_path")
    parser.add_argument("hook_command")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config_path).expanduser()
    fragment_path = Path(args.fragment_path).expanduser()
    fragment = load_json(fragment_path, {})
    fragment = replace_placeholder(fragment, shell_quote_command_path(args.hook_command))

    if args.target == "antigravity":
        merge_antigravity(config_path, fragment)
    elif args.target == "cursor":
        merge_cursor(config_path, fragment)
    else:
        merge_nested(config_path, fragment)

    print(f"Updated {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
