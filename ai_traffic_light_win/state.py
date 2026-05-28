from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATES = {"idle", "working", "waiting", "blocked"}
STATE_ALIASES = {
    "stop": "idle",
    "done": "idle",
    "complete": "idle",
    "completed": "idle",
    "thinking": "working",
    "running": "working",
    "error": "blocked",
    "failed": "blocked",
}
SOURCE_ALIASES = {
    "cc": "claude",
    "codex++": "codexpp",
    "codex-plus-plus": "codexpp",
    "codex_plus_plus": "codexpp",
}
VALID_SOURCES = {"antigravity", "cursor", "claude", "codex", "codexpp"}
PRIORITY = {"idle": 1, "working": 2, "waiting": 3, "blocked": 4}

STALE_SECONDS = {
    "idle": 0,
    "working": 15 * 60,
    "waiting": 60 * 60,
    "blocked": 60 * 60,
}


class StateError(ValueError):
    pass


def app_dir() -> Path:
    override = os.environ.get("AI_TRAFFIC_LIGHT_WIN_HOME")
    if override:
        return Path(override).expanduser()

    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "AI Traffic Light Win"

    return Path.home() / "AppData" / "Local" / "AI Traffic Light Win"


def state_file() -> Path:
    return app_dir() / "state.json"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_state(raw_state: Any) -> str:
    state = str(raw_state or "idle").lower()
    state = STATE_ALIASES.get(state, state)
    return state if state in VALID_STATES else "idle"


def normalize_source(raw_source: Any) -> str:
    source = str(raw_source or "").lower()
    source = SOURCE_ALIASES.get(source, source)
    return source if source in VALID_SOURCES else ""


def _clean_sources(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        return {}

    sources: dict[str, dict[str, str]] = {}
    for raw_source, entry in raw.items():
        source = normalize_source(raw_source)
        if not source or not isinstance(entry, dict):
            continue
        state = normalize_state(entry.get("state", "idle"))
        updated_at = str(entry.get("updated_at") or utc_now())
        sources[source] = {"state": state, "updated_at": updated_at}
    return sources


def _latest_updated_at(sources: dict[str, dict[str, str]]) -> str:
    latest_value = ""
    latest_time: datetime | None = None

    for entry in sources.values():
        value = str(entry.get("updated_at") or "")
        updated = _parse_time(value)
        if updated is None:
            continue
        if latest_time is None or updated > latest_time:
            latest_time = updated
            latest_value = value

    return latest_value


def load_document() -> dict[str, Any]:
    path = state_file()
    if not path.exists():
        return {"sources": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sources": {}}

    if isinstance(data.get("sources"), dict):
        sources = _clean_sources(data["sources"])
        updated_at = str(data.get("updated_at") or _latest_updated_at(sources) or "")
        return {"sources": sources, "updated_at": updated_at}

    source = normalize_source(data.get("source", "cursor"))
    state = normalize_state(data.get("state", "idle"))
    updated_at = data.get("updated_at", utc_now())
    if source:
        return {
            "updated_at": str(updated_at),
            "sources": {
                source: {
                    "state": state,
                    "updated_at": str(updated_at),
                }
            }
        }

    return {"sources": {}}


def pick_effective(sources: dict[str, dict[str, str]]) -> tuple[str, str]:
    has_active_source = False
    best_state = "idle"
    best_source = "none"
    best_rank = 0
    best_time = ""

    for source, entry in sources.items():
        if source not in VALID_SOURCES:
            continue
        state = normalize_state(entry.get("state", "idle"))
        if state != "idle":
            has_active_source = True
        rank = PRIORITY[state]
        updated_at = entry.get("updated_at", "")

        if rank > best_rank or (rank == best_rank and updated_at > best_time):
            best_state = state
            best_source = source
            best_rank = rank
            best_time = updated_at

    if not has_active_source:
        return "idle", best_source if best_source != "none" else "none"

    return best_state, best_source


def _persist(sources: dict[str, dict[str, str]], now: str | None = None) -> dict[str, Any]:
    app_dir().mkdir(parents=True, exist_ok=True)
    now = now or utc_now()
    effective_state, effective_source = pick_effective(sources)
    payload: dict[str, Any] = {
        "state": effective_state,
        "source": effective_source,
        "updated_at": now,
        "sources": sources,
    }

    path = state_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def write_state(raw_state: str, raw_source: str) -> dict[str, Any]:
    state = normalize_state(raw_state)
    now = utc_now()
    doc = load_document()
    sources = _clean_sources(doc.get("sources"))

    source = normalize_source(raw_source)

    if raw_source == "all":
        for source in sorted(VALID_SOURCES):
            sources[source] = {"state": state, "updated_at": now}
    elif source:
        sources[source] = {"state": state, "updated_at": now}
    else:
        raise StateError(f"invalid source: {raw_source}")

    return _persist(sources, now)


def reset_all() -> dict[str, Any]:
    now = utc_now()
    sources = {
        source: {"state": "idle", "updated_at": now}
        for source in sorted(VALID_SOURCES)
    }
    return _persist(sources, now)


def reconcile(persist_changes: bool = True) -> dict[str, Any]:
    doc = load_document()
    sources = _clean_sources(doc.get("sources"))
    now_dt = datetime.now(timezone.utc)
    now = utc_now()
    changed = False

    for source, entry in list(sources.items()):
        state = normalize_state(entry.get("state", "idle"))
        if state == "idle":
            continue

        updated = _parse_time(entry.get("updated_at"))
        if updated is None:
            continue

        stale_seconds = STALE_SECONDS[state]
        if (now_dt - updated).total_seconds() > stale_seconds:
            sources[source] = {"state": "idle", "updated_at": now}
            changed = True

    if changed and persist_changes:
        return _persist(sources, now)

    effective_state, effective_source = pick_effective(sources)
    updated_at = str(doc.get("updated_at") or _latest_updated_at(sources) or now)
    return {
        "state": effective_state,
        "source": effective_source,
        "updated_at": updated_at,
        "sources": sources,
    }
