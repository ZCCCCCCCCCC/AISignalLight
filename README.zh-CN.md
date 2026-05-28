# AI Traffic Light Win

[English](README.md)

一个专为 AI 编程助手打造的 Windows 桌面状态红绿灯。

<p align="center">
  <img src="assets/working.png" width="100" alt="Working" />
  <img src="assets/waiting.png" width="100" alt="Waiting" />
  <img src="assets/Block.png" width="100" alt="Blocked" />
  <img src="assets/Done.png" width="100" alt="Done" />
</p>

本项目使用 **Tauri + Rust** 核心重构，拥有极低的内存占用和现代化的毛玻璃（Glassmorphism）悬浮 UI，并带有动态呼吸光晕效果。

核心机制：

- **AI 状态拦截**：通过 Hooks 拦截各个 AI 工具的工作状态（支持 CLI 调用或 HTTP POST）。
- **统一状态合并**：将多个 AI 源的并行状态汇聚为 `idle`, `working`, `waiting`, `blocked` 等优先级状态。
- **全局悬浮窗**：在屏幕角落始终置顶显示当前 AI 引擎的运行状况。

## 状态含义

- 🔵 **Done / Stop** (蓝灯闪烁)：任务刚完成，请查阅。30秒后自动熄灭进入 Idle。
- 🟢 **Working** (绿灯呼吸)：AI 正在思考或自动执行代码中。
- 🟡 **Waiting** (黄灯闪烁)：等待你的授权、确认、输入或选择。
- 🔴 **Blocked** (红灯常亮)：执行出错、被拒或意外中断，需要人工介入处理。
- ⚫ **Idle** (暗色半透明)：完全空闲，没有正在进行或刚完成的任务。

如果有多个 AI 引擎同时工作，系统会遵循优先级：`blocked > waiting > working > idle` 进行高亮展示。

## 快速运行

### 1. 启动悬浮窗

直接双击 `widget.exe`，或通过命令行启动：

```powershell
python -m ai_traffic_light_win.cli widget
```

- **拖动**：可将窗口移到屏幕任意位置。
- **双击**：自动聚焦到当前活跃 AI 工具的窗口（支持终端/IDE）。
- **右键**：呼出菜单 — 重启 / 打开数据目录 / 退出。
- **系统托盘**：右下角托盘图标颜色与窗口状态联动，右键菜单同样提供 重启 / 打开目录 / 退出。

### 2. 为各路 AI 工具安装 Hooks

一键安装脚本可以自动为系统里的各个 AI 开发工具注入拦截器（Hooks）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1 -Target all
```

目前支持的自动安装目标：

- `claude` (Claude Code)
- `codex` (OpenAI Codex)
- `cursor` (Cursor Editor)
- `antigravity` (Google Antigravity)

*注：安装完成后，请重启对应的 AI 工具或编辑器，使 Hook 拦截生效。*

## 进阶功能

### 本地 HTTP Bridge 接口

Tauri 悬浮窗启动后会在后台维护一个 TCP 服务器（端口 `57422`）。
外部脚本或工具可以通过 HTTP POST 直接改变灯光状态：

```http
POST http://127.0.0.1:57422/state
Content-Type: application/json

{"state": "working", "source": "codexpp"}
```

### CLI 命令行模式

你可以自己在任意脚本中通过命令行去拨动灯的状态：

```powershell
python -m ai_traffic_light_win.cli set working codex
python -m ai_traffic_light_win.cli set waiting claude
python -m ai_traffic_light_win.cli reset
python -m ai_traffic_light_win.cli show
```

## 项目结构

```text
ai_traffic_light_win/
├── ai_traffic_light_win/
│   ├── cli.py          # 命令行入口及状态处理逻辑
│   ├── state.py        # 状态过期判断及优先级排队规则
│   ├── hook_merge.py   # Hook JSON 合并辅助工具
│   └── codex_trust.py  # 启用并信任 Codex hooks 工具
├── hooks/              # 针对 Claude, Codex, Cursor 等的 Hook 挂载片段
├── tauri-widget/       # Tauri 前端与 Rust 后端完整源码
│   ├── src/            # HTML/CSS/JS 前端样式库
│   └── src-tauri/      # Rust 后端（含窗口控制与 HTTP Server）
├── scripts/
│   └── install-hooks.ps1
├── widget.exe          # 编译好的桌面悬浮窗
├── pyproject.toml
└── README.zh-CN.md
```
