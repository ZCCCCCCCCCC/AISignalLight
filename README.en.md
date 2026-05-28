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

## What

Your AI agent runs in the background. Is it working? Waiting for input? Crashed? Instead of alt-tabbing to check, this tiny light sits in the corner of your screen and shows you at a glance.

## States

| State | Color | Meaning |
|---|---|---|
| Working | 🟢 Green | AI is running normally |
| Waiting | 🟡 Yellow (blink) | Needs your confirmation or input |
| Blocked | 🔴 Red | Error or permission denied |
| Done | 🔵 Blue (blink) | Task finished, check the result (fades after 30s) |
| Idle | ⚫ Gray | No active task |

Priority when multiple agents run: Blocked > Waiting > Working > Idle.

## Usage

Download `AISignalLight-V0.1.exe` from [Releases](https://github.com/ZCCCCCCCCCC/AISignalLight/releases) and double-click. No installation, no dependencies.

**Interaction:**

| Action | Result |
|---|---|
| Drag | Move the widget |
| Double-click | Focus the active AI tool's window |
| Right-click | Reset / Restart / Open Folder / Quit |
| Tray right-click | Same, plus toggle auto-start |

**Install AI tool hooks:**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1 -Target all
```

Supports Claude Code, Cursor, Codex, Antigravity. Restart the AI tool after installation.

## Advanced

**HTTP Bridge** on port `57422`:

```http
POST http://127.0.0.1:57422/state
Content-Type: application/json

{"state": "working", "source": "codexpp"}
```

**CLI:**

```powershell
python -m ai_traffic_light_win.cli set working claude
python -m ai_traffic_light_win.cli reset
python -m ai_traffic_light_win.cli show
```

## Build from source

```bash
cd tauri-widget
npm install
npm run tauri build
```

Requires Rust, Node.js, Windows.

## License

MIT
