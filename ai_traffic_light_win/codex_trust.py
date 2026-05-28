from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

MARKER = "ai-traffic-light-win"


def find_codex_binary() -> str | None:
    env_path = os.environ.get("CODEX_CLI_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    local_bin = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    if local_bin.exists():
        candidates = sorted(
            local_bin.glob("*/codex.exe"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])

    found = shutil.which("codex")
    if found:
        return found

    return None


def ensure_hooks_feature(config_path: Path | None = None) -> bool:
    path = config_path or Path.home() / ".codex" / "config.toml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    changed = False

    for deprecated in ("codex_hooks = true", "codex_hooks=true", "codex_hooks = false", "codex_hooks=false"):
        if deprecated in text:
            text = text.replace(deprecated, "")
            changed = True

    if "hooks = true" not in text and "hooks=true" not in text:
        if "[features]" in text:
            text = text.replace("[features]", "[features]\nhooks = true", 1)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n[features]\nhooks = true\n"
        changed = True

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return changed


class AppServerClient:
    def __init__(self, codex_binary: str) -> None:
        self._proc = subprocess.Popen(
            [codex_binary, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._messages: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._next_id = 1
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    def _read_stdout(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            with self._lock:
                self._messages.append(message)

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any]:
        assert self._proc.stdin is not None
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for message in self._messages:
                    if message.get("id") != request_id:
                        continue
                    if "error" in message:
                        error = message["error"]
                        if isinstance(error, dict):
                            raise RuntimeError(error.get("message", "app-server error"))
                        raise RuntimeError(str(error))
                    result = message.get("result", {})
                    return result if isinstance(result, dict) else {}
            time.sleep(0.05)
        raise TimeoutError(f"Timed out waiting for {method}")


def list_hooks(client: AppServerClient, cwd: Path) -> list[dict[str, Any]]:
    result = client.request("hooks/list", {"cwds": [str(cwd)]})
    data = result.get("data") or []
    if not isinstance(data, list) or not data:
        return []
    hooks = data[0].get("hooks") if isinstance(data[0], dict) else []
    return hooks if isinstance(hooks, list) else []


def trust_hooks(client: AppServerClient, hooks: list[dict[str, Any]]) -> int:
    edits = []
    for hook in hooks:
        command = str(hook.get("command") or "")
        if MARKER not in command:
            continue
        if hook.get("trustStatus") == "trusted":
            continue
        key = hook.get("key")
        current_hash = hook.get("currentHash")
        if not key or not current_hash:
            continue
        edits.append(
            {
                "keyPath": f'hooks.state."{escape_key_path_segment(str(key))}"',
                "mergeStrategy": "upsert",
                "value": {"trusted_hash": current_hash},
            }
        )

    if not edits:
        return 0

    client.request("config/batchWrite", {"edits": edits})
    return len(edits)


def escape_key_path_segment(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-trust")
    parser.add_argument("--cwd", default=str(Path.home()), help="workspace directory Codex should evaluate")
    parser.add_argument("--codex", default=None, help="path to codex.exe")
    parser.add_argument("--list", action="store_true", help="print detected hook commands before trusting")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_hooks_feature()

    codex_binary = args.codex or find_codex_binary()
    if codex_binary is None:
        print("Codex CLI not found; skipped hook trust", file=sys.stderr)
        return 0

    client = AppServerClient(codex_binary)
    try:
        client.request(
            "initialize",
            {
                "clientInfo": {"name": "ai-traffic-light-win", "version": "1.0"},
                "capabilities": {},
            },
        )
        hooks = list_hooks(client, Path(args.cwd))
        managed_hooks = [hook for hook in hooks if MARKER in str(hook.get("command") or "")]
        if args.list:
            print(json.dumps(managed_hooks, indent=2, ensure_ascii=False))

        trusted_count = trust_hooks(client, hooks)
        if trusted_count:
            print(f"Trusted {trusted_count} Codex hook(s)")
        elif managed_hooks:
            print("Codex hooks already trusted")
        else:
            print("Codex hooks not visible to app-server yet")
        return 0
    except Exception as exc:
        print(f"Failed to trust Codex hooks: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
