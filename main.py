import asyncio
import subprocess
import time
from collections import deque
from typing import Any, Dict, Optional

import psutil
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Optional dependency: pynvml. If unavailable, we gracefully fall back to nvidia-smi.
try:
    import pynvml  # type: ignore

    PYNVML_AVAILABLE = True
except Exception:
    pynvml = None
    PYNVML_AVAILABLE = False


class GpuReader:
    """Read GPU utilization with graceful fallback.

    Priority:
    1) NVIDIA NVML via pynvml
    2) nvidia-smi command
    3) unavailable
    """

    def __init__(self) -> None:
        self.mode = "none"
        self.error_message = "GPU unavailable"
        self._nvml_initialized = False
        self._detect()

    def _detect(self) -> None:
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    self.mode = "pynvml"
                    self._nvml_initialized = True
                    self.error_message = ""
                    return
            except Exception as exc:
                self.error_message = f"pynvml init failed: {exc}"

        # Try nvidia-smi fallback.
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                self.mode = "nvidia-smi"
                self.error_message = ""
                return
            self.error_message = (
                result.stderr.strip() or "nvidia-smi returned empty output"
            )
        except Exception as exc:
            self.error_message = f"nvidia-smi unavailable: {exc}"

    def read_usage(self) -> Dict[str, Any]:
        if self.mode == "pynvml":
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                return {
                    "available": True,
                    "usage": float(util.gpu),
                    "source": "pynvml",
                    "message": "",
                }
            except Exception as exc:
                return {
                    "available": False,
                    "usage": None,
                    "source": "pynvml",
                    "message": f"read failed: {exc}",
                }

        if self.mode == "nvidia-smi":
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if result.returncode != 0:
                    return {
                        "available": False,
                        "usage": None,
                        "source": "nvidia-smi",
                        "message": result.stderr.strip() or "command failed",
                    }

                lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if not lines:
                    return {
                        "available": False,
                        "usage": None,
                        "source": "nvidia-smi",
                        "message": "empty output",
                    }

                # For multi-GPU machines, average usage for a simple single-number panel.
                values = [float(v) for v in lines]
                avg = sum(values) / len(values)
                return {
                    "available": True,
                    "usage": round(avg, 2),
                    "source": "nvidia-smi",
                    "message": "",
                }
            except Exception as exc:
                return {
                    "available": False,
                    "usage": None,
                    "source": "nvidia-smi",
                    "message": f"read failed: {exc}",
                }

        return {
            "available": False,
            "usage": None,
            "source": "none",
            "message": self.error_message,
        }

    def close(self) -> None:
        if self._nvml_initialized and PYNVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


class MetricsStore:
    """In-memory recent metrics history for chart data and diagnostics."""

    def __init__(self, maxlen: int = 120) -> None:
        self.maxlen = maxlen
        self.cpu = deque(maxlen=maxlen)
        self.gpu = deque(maxlen=maxlen)
        self.timestamps = deque(maxlen=maxlen)

    def push(self, cpu: float, gpu: Optional[float], ts: float) -> None:
        self.cpu.append(cpu)
        self.gpu.append(gpu)
        self.timestamps.append(ts)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "timestamps": list(self.timestamps),
            "cpu": list(self.cpu),
            "gpu": list(self.gpu),
        }


app = FastAPI(title="nodeWatch", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

gpu_reader = GpuReader()
metrics_store = MetricsStore(maxlen=180)

# Prime psutil's CPU calculator to avoid the first call always being 0.0.
psutil.cpu_percent(interval=None)


async def collect_status() -> Dict[str, Any]:
    cpu_usage = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    gpu = gpu_reader.read_usage()
    ts = time.time()

    metrics_store.push(cpu=cpu_usage, gpu=gpu["usage"], ts=ts)

    return {
        "timestamp": ts,
        "cpu": {
            "usage": round(cpu_usage, 2),
        },
        "memory": {
            "usage": round(memory.percent, 2),
            "used_mb": round(memory.used / 1024 / 1024, 2),
            "total_mb": round(memory.total / 1024 / 1024, 2),
        },
        "gpu": gpu,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    # Use keyword arguments for compatibility across Starlette versions.
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "project_name": "nodeWatch",
        },
    )


@app.get("/status", response_class=JSONResponse)
async def status() -> JSONResponse:
    data = await collect_status()
    return JSONResponse(content=data)


@app.get("/history", response_class=JSONResponse)
async def history() -> JSONResponse:
    return JSONResponse(content=metrics_store.snapshot())


@app.websocket("/ws")
async def websocket_status(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            data = await collect_status()
            await ws.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    except Exception:
        await ws.close()


@app.on_event("shutdown")
def on_shutdown() -> None:
    gpu_reader.close()


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0 allows LAN clients to access this service.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
