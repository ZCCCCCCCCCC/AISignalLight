# AISignalLight

[English](README.en.md)

[![Download](https://img.shields.io/badge/下载-Releases-blue)](https://github.com/ZCCCCCCCCCC/AISignalLight/releases)

AI 编程助手桌面状态指示灯 —— 一个小巧的悬浮窗，告诉你 AI 当前在干什么。

<p align="center">
  <img src="assets/working.png" width="100" alt="Working" />
  <img src="assets/waiting.png" width="100" alt="Waiting" />
  <img src="assets/Block.png" width="100" alt="Blocked" />
  <img src="assets/Done.png" width="100" alt="Done" />
</p>

## 它是什么

写代码时 AI 助手的运行状态你是看不到的 —— 它在跑还是卡住了？在等你确认还是报错了？每次都要切回窗口看。

这个小灯悬浮在桌面角落，通过 Hook 自动获取 AI 工具的实时状态，一眼就知道该不该切回去。

## 状态

| 颜色 | 状态 | 含义 |
|---|---|---|
| 🟢 绿色 | Working | AI 正在工作中 |
| 🟡 黄色（闪烁） | Waiting | 等待你的确认或输入 |
| 🔴 红色 | Blocked | 执行出错或被拒绝 |
| 🔵 蓝色（闪烁） | Done | 任务完成，请查阅（30 秒后熄灭） |
| ⚫ 灰色 | Idle | 空闲 |

多个 AI 同时运行时，优先级：Blocked > Waiting > Working > Idle。

## 使用

从 [Releases](https://github.com/ZCCCCCCCCCC/AISignalLight/releases) 下载 `AISignalLight-V0.1.exe`，双击运行。无需安装。

**交互：**

| 操作 | 效果 |
|---|---|
| 拖动 | 移动悬浮窗 |
| 双击 | 切到当前活跃 AI 工具的窗口 |
| 右键 | Reset / 重启 / 打开目录 / 退出 |
| 托盘右键 | 同上，外加开关机自启 |

**安装 AI 工具钩子：**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-hooks.ps1 -Target all
```

支持 Claude Code、Cursor、Codex、Antigravity。装完重启对应的 AI 工具生效。

## 进阶

**HTTP Bridge**（端口 `57422`），外部脚本可直接改状态：

```http
POST http://127.0.0.1:57422/state
Content-Type: application/json

{"state": "working", "source": "codexpp"}
```

**CLI：**

```powershell
python -m ai_traffic_light_win.cli set working claude
python -m ai_traffic_light_win.cli reset
python -m ai_traffic_light_win.cli show
```

## 从源码构建

```bash
cd tauri-widget
npm install
npm run tauri build
```

要求：Rust、Node.js、Windows。

## 项目结构

```text
├── ai_traffic_light_win/   # Python 状态引擎（CLI + Hook 合并）
├── tauri-widget/           # 悬浮窗源码（Tauri + HTML/CSS/JS）
├── hooks/                  # 各 AI 工具 Hook 模板
└── scripts/                # 安装脚本
```

## License

MIT
