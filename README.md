# nodeWatch

nodeWatch 是一个运行在个人电脑上的局域网系统监控面板。它会通过 Web 页面实时展示本机的 CPU、内存、GPU 使用率，并支持同一局域网中的其他设备访问。

## 功能特性

- 实时指标（1 秒刷新，基于 WebSocket）：
  - CPU 使用率
  - 内存使用率（含已用/总量）
  - GPU 使用率
- GPU 检测支持优先级：
  1. `pynvml`（NVIDIA NVML）
  2. `nvidia-smi` 命令
  3. 不可用时优雅降级（前端显示 N/A 和原因）
- 前端图表：
  - CPU 曲线
  - GPU 曲线
- 支持局域网访问（服务监听 `0.0.0.0`）

## 项目结构

```text
nodeWatch/
├─ main.py
├─ requirements.txt
├─ templates/
│  └─ index.html
├─ static/
│  ├─ css/
│  │  └─ style.css
│  └─ js/
│     └─ app.js
└─ README.md
```

## 运行环境

- Python 3.10+
- Windows / Linux / macOS
- （可选）NVIDIA GPU 与驱动（用于 GPU 实时监控）

## 安装依赖

在项目根目录执行：

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux / macOS
# source .venv/bin/activate

pip install -r requirements.txt
```

## 启动服务

方式 1（推荐）：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

方式 2：

```bash
python main.py
```

## 访问方式

1. 本机访问：
   - `http://127.0.0.1:8000`
2. 局域网访问：
   - `http://你的本机IP:8000`

在 Windows 可以执行以下命令查看本机 IP：

```powershell
ipconfig
```

找到当前网络适配器的 IPv4 地址，例如 `192.168.1.23`，那么局域网其他设备可访问：

- `http://192.168.1.23:8000`

## API 说明

- `GET /status`
  - 返回当前一次系统状态快照（CPU/内存/GPU）
- `GET /history`
  - 返回服务启动后的最近历史数据（用于调试或扩展）
- `WS /ws`
  - 每秒推送一次最新状态，前端默认使用该接口实时更新

## 注意事项

- 若系统没有 NVIDIA GPU、未安装驱动、或 `nvidia-smi` 不可用，GPU 指标会显示 `N/A`，不影响其他监控功能。
- 若局域网设备无法访问，请检查：
  - 防火墙是否允许 8000 端口入站
  - 本机与访问设备是否在同一网段

## 后续可扩展方向

- 增加磁盘、网络吞吐、CPU 温度等监控项
- 增加鉴权（如 Basic Auth / Token）
- 使用数据库持久化历史监控数据
