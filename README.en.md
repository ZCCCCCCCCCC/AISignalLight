# AISignalLight

[中文说明](README.md)

[![Download](https://img.shields.io/badge/Download-Releases-blue)](https://github.com/ZCCCCCCCCCC/AISignalLight/releases)

A tiny floating desktop indicator that shows your AI coding agent's real-time status.

<p align="center">
  <img src="assets/working.png" width="100" alt="Working" />
  <img src="assets/waiting.png" width="100" alt="Waiting" />
  <img src="assets/Block.png" width="100" alt="Blocked" />
  <img src="assets/Done.png" width="100" alt="Done" />
</p>

## States

| | Color | Meaning |
|---|---|---|
| Working | 🟢 Green | AI is running |
| Waiting | 🟡 Yellow (blink) | Needs your confirmation or input |
| Blocked | 🔴 Red | Error or permission denied |
| Done | 🔵 Blue (blink) | Task finished (fades after 30s) |
| Idle | ⚫ Gray | No active task |

Priority across agents: Blocked > Waiting > Working > Idle.

---

## For Users

Download `AISignalLight-V0.1.exe` from [Releases](https://github.com/ZCCCCCCCCCC/AISignalLight/releases), double-click to run. No installation, no dependencies.

| Action | Result |
|---|---|
| Drag | Move the widget |
| Double-click | Focus active AI tool's window |
| Right-click | Reset / Restart / Open Folder / Quit |
| Tray right-click | Same + toggle auto-start |

### Connect AI tools

To let Claude Code, Cursor, etc. report their status automatically, install hooks.

Hooks are tiny scripts your AI tool calls when working, waiting, or hitting errors. The light follows along.

Make sure `AISignalLight-V0.1.exe` is running, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1 -Target all
```

Targets: `claude`, `codex`, `cursor`, `antigravity`. Restart the AI tool afterwards.

---

## For Developers

### Build from source

```bash
cd tauri-widget
npm install
npm run tauri build
```

Requires Rust + Node.js + Windows.

### HTTP Bridge

The exe listens on `127.0.0.1:57422`. Any external tool can post state changes:

```http
POST http://127.0.0.1:57422/state
Content-Type: application/json

{"state": "working", "source": "codexpp"}
```

### CLI

```powershell
python -m ai_traffic_light_win.cli set working claude
python -m ai_traffic_light_win.cli reset
python -m ai_traffic_light_win.cli show
```

### Structure

```text
├── ai_traffic_light_win/   # Python state engine (CLI + hook merge)
├── tauri-widget/           # Widget source (Tauri + HTML/CSS/JS)
├── hooks/                  # AI tool hook fragments
└── scripts/                # Install scripts
```

## License

MIT
