# AI Traffic Light Win

[中文说明](README.zh-CN.md)

A modern, lightweight Windows floating traffic-light widget for AI coding agents.

<p align="center">
  <img src="assets/working.png" width="100" alt="Working" />
  <img src="assets/waiting.png" width="100" alt="Waiting" />
  <img src="assets/Block.png" width="100" alt="Blocked" />
  <img src="assets/Done.png" width="100" alt="Done" />
</p>

This project is a fresh Windows implementation providing a beautifully animated, always-on-top indicator for your AI agents. It uses **Tauri + Rust** for extreme performance and minimal footprint, featuring glassmorphism design and glowing animations.

- **Agent Hooks**: AI tools report their current state using either CLI commands or local HTTP POST.
- **State File**: A small local JSON file stores priorities (`idle`, `working`, `waiting`, or `blocked`).
- **Floating Widget**: An always-on-top, draggable traffic light with a translucent background that watches state changes.

## States

- 🔵 **Done / Stop**: Blue blinking. The task finished and is ready to review. Reverts to Idle after 30 seconds.
- 🟢 **Working**: Green with a breathing glow. The agent is making normal progress.
- 🟡 **Waiting**: Yellow blinking. The agent needs user confirmation, authorization, or input.
- 🔴 **Blocked**: Red. An error or denial stopped progress.
- ⚫ **Idle**: Dimmed grey. The system is completely idle.

When multiple sources are active, the effective priority is `blocked > waiting > working > idle`.

## Getting Started

### 1. Run the Widget

Double-click `widget.exe`, or via CLI:

```powershell
python -m ai_traffic_light_win.cli widget
```

- **Drag**: Move the floating widget anywhere.
- **Double-click**: Bring the active AI tool's window to front (terminal or IDE).
- **Right-click**: Quick menu — Restart / Open Folder / Quit.
- **System Tray**: Tray icon color syncs with current state. Right-click the tray icon for Restart / Open Folder / Quit.

### 2. Install Hooks for AI Agents

Run the installation script in PowerShell to automatically deploy hooks to your AI tools:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1 -Target all
```

Supported targets:

- `claude` (Claude Code)
- `codex` (OpenAI Codex)
- `cursor` (Cursor Editor)
- `antigravity` (Google Antigravity)

*Restart the relevant app after installing hooks to take effect.*

## Advanced Usage

### Local HTTP Bridge

The widget runs a lightweight TCP server on port `57422`. External scripts or tools can send HTTP POST requests to change the light state:

```http
POST http://127.0.0.1:57422/state
Content-Type: application/json

{"state": "working", "source": "codexpp"}
```

### Command Line Interface

You can manually trigger states via CLI:

```powershell
python -m ai_traffic_light_win.cli set working codex
python -m ai_traffic_light_win.cli set waiting claude
python -m ai_traffic_light_win.cli reset
python -m ai_traffic_light_win.cli show
```

## Architecture

```text
ai_traffic_light_win/
├── ai_traffic_light_win/
│   ├── cli.py          # Command line interface & state manager
│   ├── state.py        # Logic for parsing and aging state priorities
│   ├── hook_merge.py   # Utility to merge hook config fragments
│   └── codex_trust.py  # Utility to enable and trust Codex hooks
├── hooks/              # Hook fragments for Claude, Codex, Cursor, etc.
├── tauri-widget/       # Tauri Frontend / Rust Backend source code
│   ├── src/            # HTML/CSS/JS frontend
│   └── src-tauri/      # Rust backend (HTTP Bridge & OS integration)
├── scripts/
│   └── install-hooks.ps1
├── widget.exe          # Compiled widget executable
├── pyproject.toml
└── README.md
```
