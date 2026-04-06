const MAX_POINTS = 60;

const cpuValueEl = document.getElementById("cpuValue");
const memValueEl = document.getElementById("memValue");
const memDetailEl = document.getElementById("memDetail");
const gpuValueEl = document.getElementById("gpuValue");
const gpuDetailEl = document.getElementById("gpuDetail");
const connBadgeEl = document.getElementById("connBadge");
const lastUpdateEl = document.getElementById("lastUpdate");

function nowLabel() {
    return new Date().toLocaleTimeString();
}

function setConnectionStatus(connected) {
    if (connected) {
        connBadgeEl.textContent = "WebSocket 已连接";
        connBadgeEl.classList.remove("err");
        connBadgeEl.classList.add("ok");
        return;
    }
    connBadgeEl.textContent = "连接断开，自动重连中";
    connBadgeEl.classList.remove("ok");
    connBadgeEl.classList.add("err");
}

function createChart(ctx, label, color) {
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label,
                    data: [],
                    borderColor: color,
                    backgroundColor: color.replace(")", ", 0.18)").replace("rgb", "rgba"),
                    tension: 0.28,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    ticks: {
                        color: "#9db0c7",
                        maxTicksLimit: 6,
                    },
                    grid: {
                        color: "rgba(255,255,255,0.06)",
                    },
                },
                y: {
                    min: 0,
                    max: 100,
                    ticks: {
                        color: "#9db0c7",
                        callback: (v) => `${v}%`,
                    },
                    grid: {
                        color: "rgba(255,255,255,0.06)",
                    },
                },
            },
            plugins: {
                legend: {
                    labels: {
                        color: "#e9f1ff",
                    },
                },
            },
        },
    });
}

const cpuChart = createChart(
    document.getElementById("cpuChart"),
    "CPU",
    "rgb(79, 163, 255)"
);

const gpuChart = createChart(
    document.getElementById("gpuChart"),
    "GPU",
    "rgb(41, 199, 172)"
);

function pushPoint(chart, label, value) {
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(value);

    if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update("none");
}

function renderStatus(payload) {
    const cpuUsage = payload.cpu?.usage ?? 0;
    const memUsage = payload.memory?.usage ?? 0;

    cpuValueEl.textContent = `${cpuUsage.toFixed(1)}%`;
    memValueEl.textContent = `${memUsage.toFixed(1)}%`;

    const used = payload.memory?.used_mb ?? 0;
    const total = payload.memory?.total_mb ?? 0;
    memDetailEl.textContent = `${used.toFixed(0)} MB / ${total.toFixed(0)} MB`;

    if (payload.gpu?.available) {
        const gpuUsage = payload.gpu.usage ?? 0;
        gpuValueEl.textContent = `${Number(gpuUsage).toFixed(1)}%`;
        gpuDetailEl.textContent = `来源: ${payload.gpu.source}`;
        pushPoint(gpuChart, nowLabel(), Number(gpuUsage));
    } else {
        gpuValueEl.textContent = "N/A";
        gpuDetailEl.textContent = payload.gpu?.message || "当前设备不可用";
        // Keep chart scale stable when GPU is unavailable.
        pushPoint(gpuChart, nowLabel(), null);
    }

    pushPoint(cpuChart, nowLabel(), Number(cpuUsage));

    lastUpdateEl.textContent = `最后更新: ${nowLabel()}`;
}

function startWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${protocol}://${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        setConnectionStatus(true);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            renderStatus(data);
        } catch (err) {
            console.error("Invalid WS payload:", err);
        }
    };

    ws.onclose = () => {
        setConnectionStatus(false);
        setTimeout(startWebSocket, 1500);
    };

    ws.onerror = () => {
        ws.close();
    };
}

setConnectionStatus(false);
startWebSocket();
