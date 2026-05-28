from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .state import SOURCE_ALIASES, VALID_SOURCES, VALID_STATES, StateError, app_dir, reconcile, reset_all, write_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-traffic-light-win")
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command")

    set_parser = subparsers.add_parser("set", help="set a state for a source")
    set_parser.add_argument(
        "state",
        choices=sorted(VALID_STATES | {"complete", "completed", "done", "error", "failed", "running", "stop", "thinking"}),
    )
    set_parser.add_argument("source", choices=sorted(VALID_SOURCES | set(SOURCE_ALIASES) | {"all"}))

    hook_parser = subparsers.add_parser("hook", help="set state and emit hook-compatible JSON")
    hook_parser.add_argument("event", help="hook event name, such as PreToolUse or Stop")
    hook_parser.add_argument(
        "state",
        choices=sorted(VALID_STATES | {"complete", "completed", "done", "error", "failed", "running", "stop", "thinking"}),
    )
    hook_parser.add_argument("source", choices=sorted(VALID_SOURCES | set(SOURCE_ALIASES) | {"all"}))

    subparsers.add_parser("reset", help="reset all sources to idle")
    subparsers.add_parser("show", help="print the effective state as JSON")
    subparsers.add_parser("path", help="print the state directory")
    subparsers.add_parser("widget", help="launch the floating widget")

    return parser


def read_hook_stdin() -> dict[str, object]:
    if sys.stdin.isatty():
        return {}

    try:
        text = sys.stdin.read(1_048_576)
    except OSError:
        return {}

    if not text.strip():
        return {}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def hook_response(event: str) -> dict[str, object]:
    if event == "PreToolUse":
        return {"decision": "allow"}
    if event == "PreInvocation":
        return {"injectSteps": []}
    if event == "PostInvocation":
        return {"injectSteps": [], "terminationBehavior": ""}
    if event == "Stop":
        return {"decision": ""}
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "set":
            payload = write_state(args.state, args.source)
            print(payload["state"])
            return 0

        if args.command == "hook":
            state = args.state
            stdin_payload = read_hook_stdin()
            if args.event == "Stop" and stdin_payload.get("fullyIdle") is False:
                state = "working"

            write_state(state, args.source)
            print(json.dumps(hook_response(args.event), separators=(",", ":")))
            return 0

        if args.command == "reset":
            payload = reset_all()
            print(payload["state"])
            return 0

        if args.command == "show":
            print(json.dumps(reconcile(), indent=2, sort_keys=True))
            return 0

        if args.command == "path":
            print(app_dir())
            return 0

        if args.command == "widget":
            import subprocess
            from pathlib import Path
            root = Path(__file__).parent.parent
            candidates = sorted(root.glob("AISignalLight*.exe"))
            if not candidates:
                print("AISignalLight*.exe not found", file=sys.stderr)
                return 1
            subprocess.Popen([str(candidates[-1])], creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
            return 0

    except StateError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
