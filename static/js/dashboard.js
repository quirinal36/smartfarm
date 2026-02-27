// SmartFarm Dashboard Logic

let selectedZone = null;
let chart = null;
let latestData = [];
let systemInfo = {};

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    fetchLatest();
    fetchAiLogs();
    fetchSystem();
    startClock();

    setInterval(fetchLatest, 10000);
    setInterval(fetchAiLogs, 60000);
    setInterval(fetchSystem, 30000);
});

// --- Clock ---
function startClock() {
    function tick() {
        const now = new Date();
        document.getElementById('clock-date').textContent = now.toLocaleDateString('ko-KR');
        document.getElementById('clock-time').textContent = now.toLocaleTimeString('ko-KR');
    }
    tick();
    setInterval(tick, 1000);
}

// --- Fetch Latest Sensor Data ---
async function fetchLatest() {
    try {
        const res = await fetch('/api/latest');
        if (res.status === 401 || res.redirected) { location.href = '/login'; return; }
        const json = await res.json();
        latestData = json.data;

        const mockBadge = document.getElementById('mode-badge');
        if (json.mock) {
            mockBadge.textContent = 'MOCK';
            mockBadge.className = 'badge badge-mock';
        } else {
            mockBadge.textContent = 'LIVE';
            mockBadge.className = 'badge badge-active';
        }

        renderZoneCards();
        if (selectedZone) fetchHistory(selectedZone);
    } catch (e) {
        console.error('fetchLatest error:', e);
    }
}

// --- Render Zone Cards ---
function renderZoneCards() {
    const container = document.getElementById('zone-list');
    container.innerHTML = '';

    latestData.forEach((node, idx) => {
        const status = getStatus(node);
        const card = document.createElement('div');
        card.className = 'zone-card' + (selectedZone === node.id ? ' selected' : '');
        card.onclick = () => selectZone(node.id);

        card.innerHTML = `
            <div class="zone-header">
                <div>
                    <span class="zone-id">${node.id}</span>
                    <div class="zone-name">${node.name}</div>
                </div>
                <span class="status-dot status-${status}"></span>
            </div>
            <div class="zone-readings">
                <div class="reading">
                    <div class="label">온도</div>
                    <div class="value temp-value">${node.temp !== null ? node.temp : '--'}<span class="unit">°C</span></div>
                </div>
                <div class="reading">
                    <div class="label">습도</div>
                    <div class="value humi-value">${node.humi !== null ? node.humi : '--'}<span class="unit">%</span></div>
                </div>
            </div>
            <div class="device-status">
                <span class="device-badge ${node.fan ? 'device-on' : 'device-off'}">환풍기 ${node.fan ? 'ON' : 'OFF'}</span>
                <span class="device-badge ${node.heater ? 'device-on' : 'device-off'}">히터 ${node.heater ? 'ON' : 'OFF'}</span>
                <span class="device-badge ${node.humid ? 'device-on' : 'device-off'}">가습기 ${node.humid ? 'ON' : 'OFF'}</span>
            </div>
            <div class="zone-controls">
                <button class="ctrl-btn ${node.fan ? 'active' : ''}" onclick="event.stopPropagation(); toggleDevice('${node.id}', 'fan', ${!node.fan})">환풍기</button>
                <button class="ctrl-btn ${node.heater ? 'active' : ''}" onclick="event.stopPropagation(); toggleDevice('${node.id}', 'heater', ${!node.heater})">히터</button>
                <button class="ctrl-btn ${node.humid ? 'active' : ''}" onclick="event.stopPropagation(); toggleDevice('${node.id}', 'humidifier', ${!node.humid})">가습기</button>
            </div>
        `;
        container.appendChild(card);

        // auto-select first zone
        if (idx === 0 && !selectedZone) selectZone(node.id);
    });
}

function getStatus(node) {
    if (!node.online) return 'offline';
    if (node.temp === null) return 'offline';
    // find crop ranges from hardcoded defaults
    const ranges = {
        '토마토': { tMin: 18, tMax: 30, hMax: 80 },
        '딸기':   { tMin: 15, tMax: 25, hMax: 80 },
        '상추':   { tMin: 15, tMax: 25, hMax: 70 },
    };
    const r = ranges[node.crop] || { tMin: 15, tMax: 30, hMax: 80 };

    if (node.temp > r.tMax + 10 || node.temp < r.tMin - 10 || node.humi > 90) return 'danger';
    if (node.temp > r.tMax + 5  || node.temp < r.tMin - 5  || node.humi > 80) return 'warn';
    if (node.temp > r.tMax || node.temp < r.tMin) return 'warn';
    return 'ok';
}

// --- Zone Selection & Chart ---
function selectZone(zoneId) {
    selectedZone = zoneId;
    document.querySelectorAll('.zone-card').forEach(c => c.classList.remove('selected'));
    const cards = document.querySelectorAll('.zone-card');
    latestData.forEach((n, i) => {
        if (n.id === zoneId && cards[i]) cards[i].classList.add('selected');
    });
    document.getElementById('chart-title').textContent =
        `${zoneId} 추이 (12시간)`;
    fetchHistory(zoneId);
}

async function fetchHistory(deviceId) {
    try {
        const res = await fetch(`/api/history/${deviceId}?hours=12`);
        const json = await res.json();
        renderChart(json.data);
    } catch (e) {
        console.error('fetchHistory error:', e);
    }
}

function renderChart(data) {
    const ctx = document.getElementById('main-chart').getContext('2d');

    const labels = data.map(d => {
        const t = new Date(d.timestamp + 'Z');
        return t.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    });
    const temps = data.map(d => d.temp);
    const humis = data.map(d => d.humi);

    if (chart) chart.destroy();

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: '온도 (°C)',
                    data: temps,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255,107,107,0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                    yAxisID: 'y',
                },
                {
                    label: '습도 (%)',
                    data: humis,
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78,205,196,0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: '#888', font: { size: 11 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#555', maxTicksLimit: 12, font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    position: 'left',
                    title: { display: true, text: '°C', color: '#ff6b6b' },
                    ticks: { color: '#ff6b6b', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y1: {
                    position: 'right',
                    title: { display: true, text: '%', color: '#4ecdc4' },
                    ticks: { color: '#4ecdc4', font: { size: 10 } },
                    grid: { drawOnChartArea: false },
                }
            }
        }
    });
}

// --- System Info ---
async function fetchSystem() {
    try {
        const res = await fetch('/api/system');
        const json = await res.json();
        systemInfo = json;

        document.getElementById('sys-cpu').textContent =
            json.cpu_temp !== null ? json.cpu_temp + '°C' : 'N/A';
        document.getElementById('sys-uptime').textContent = json.uptime || 'N/A';
        document.getElementById('sys-nodes').textContent =
            `${json.online_count}/${json.node_count}`;
    } catch (e) {
        console.error('fetchSystem error:', e);
    }
}

// --- AI Logs ---
async function fetchAiLogs() {
    try {
        const res = await fetch('/api/ai-logs?limit=20');
        const json = await res.json();
        renderAiLogs(json.logs);
    } catch (e) {
        console.error('fetchAiLogs error:', e);
    }
}

function renderAiLogs(logs) {
    const container = document.getElementById('ai-log-list');
    container.innerHTML = '';

    if (logs.length === 0) {
        container.innerHTML = '<div class="ai-summary">AI 로그가 아직 없습니다.</div>';
        return;
    }

    logs.forEach(log => {
        const item = document.createElement('div');
        item.className = 'ai-log-item' + (log.alert ? ' has-alert' : '');

        const ts = log.timestamp ? new Date(log.timestamp + 'Z').toLocaleTimeString('ko-KR', {
            hour: '2-digit', minute: '2-digit'
        }) : '';

        item.innerHTML = `
            <div>
                <span class="ai-log-time">${ts}</span>
                <span class="ai-log-device">${log.device_id}</span>
            </div>
            <div class="ai-log-action">${log.action || '유지'}</div>
            <div class="ai-log-reason">${log.reason || ''}</div>
            ${log.alert ? `<div class="ai-log-reason" style="color:var(--danger);">${log.alert}</div>` : ''}
        `;
        container.appendChild(item);
    });
}

// --- Manual Control ---
async function toggleDevice(deviceId, device, state) {
    const node = latestData.find(n => n.id === deviceId);
    if (!node) return;

    const cmd = {
        device_id: deviceId,
        fan: device === 'fan' ? state : !!node.fan,
        heater: device === 'heater' ? state : !!node.heater,
        humidifier: device === 'humidifier' ? state : !!node.humid,
    };

    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cmd),
        });
        const json = await res.json();
        if (json.success) {
            fetchLatest();
        }
    } catch (e) {
        console.error('command error:', e);
    }
}
