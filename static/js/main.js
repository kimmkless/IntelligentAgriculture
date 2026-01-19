// JavaScript主文件
let temperatureChart = null;
let systemStartTime = new Date();
let currentHours = 24;

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    refreshData();
    setInterval(refreshData, 10000); // 每10秒刷新一次

    initTemperatureChart();
    updateUptime();
    setInterval(updateUptime, 60000);
});

function handleTimeChange() {
    const selector = document.getElementById('timeRange');
    currentHours = parseFloat(selector.value); // 确保是数字
    
    // 视觉反馈：切换时降低图表透明度，表示正在加载
    const canvas = document.getElementById('temperatureChart');
    canvas.style.opacity = '0.5';
    
    fetchHistoryData();
}

function updateUptime() {
    const now = new Date();
    const diff = now - systemStartTime;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    document.getElementById('uptime').textContent = `${days}天${hours}小时`;
}

function initTemperatureChart() {
    const ctx = document.getElementById('temperatureChart').getContext('2d');
    temperatureChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '温度 (°C)',
                data: [],
                borderColor: '#4299e1',
                backgroundColor: 'rgba(66, 153, 225, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    min: 0,
                    max: 50,
                    grid: {
                        color: '#e2e8f0'
                    },
                    title: {
                        display: true,
                        text: '温度 (°C)'
                    },
                    ticks: {
                        stepSize: 5
                    }
                }
            }
        }
    });
}

function refreshData() {
    // 更新系统概览
    fetch('/api/system/status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('onlineDevices').textContent = data.active_devices || 0;
            document.getElementById('todayData').textContent = data.today_readings || 0;
        });

    // 获取最新传感器数据
    fetch('/api/data/latest?limit=5')
        .then(response => response.json())
        .then(data => {
            if (data.data && data.data.length > 0) {
                const latest = data.data[0];
                document.getElementById('temperature').textContent =
                    `${latest.temperature ? latest.temperature.toFixed(1) : '--'} °C`;
                document.getElementById('humidity').textContent =
                    `${latest.humidity ? latest.humidity.toFixed(1) : '--'} %`;
                document.getElementById('pm25').textContent =
                    `${latest.pm25 || '--'} μg/m³`;
                document.getElementById('light').textContent =
                    `${latest.light_lux || '--'} lux`;

                updateDataTable(data.data);
            }
        });

    // 获取设备统计
    fetch('/api/statistics/device/SmartAgriculture_thermometer')
        .then(response => response.json())
        .then(data => {
            document.getElementById('dataQuality').textContent =
                data.avg_quality ? `${data.avg_quality.toFixed(1)}%` : '-- %';
        });

    // 获取历史数据用于图表，修改hours的取值来显示不同时间内的数据
    fetch(`1/api/data/history?device_id=SmartAgriculture_thermometer&hours=${currentHours}`)
        .then(response => response.json())
        .then(data => {
            updateTemperatureChart(data.data);
        });
}

function fetchHistoryData() {
    fetch(`/api/data/history?device_id=SmartAgriculture_thermometer&hours=${currentHours}`)
        .then(response => response.json())
        .then(data => {
            updateTemperatureChart(data.data);
        })
        .catch(err => console.error("获取历史数据失败:", err));
}

function updateDataTable(data) {
    const tbody = document.getElementById('dataTableBody');
    tbody.innerHTML = '';

    data.forEach(item => {
        const row = document.createElement('tr');
        const time = new Date(item.timestamp).toLocaleString('zh-CN');

        row.innerHTML = `
            <td>${time}</td>
            <td>${item.device_id || '--'}</td>
            <td>${item.temperature ? item.temperature.toFixed(1) : '--'}</td>
            <td>${item.humidity ? item.humidity.toFixed(1) : '--'}</td>
            <td>${item.pm25 || '--'}</td>
            <td>${item.light_lux || '--'}</td>
        `;
        tbody.appendChild(row);
    });
}

function updateTemperatureChart(data) {
    if (!temperatureChart || !data|| data.length === 0) return;
    
    let maxPoints;
    if (currentHours <= 4)          maxPoints = 40;
    else if (currentHours <= 24)    maxPoints = 60;
    else                            maxPoints = 80; // 1周的数据

    const labels = [];
    const temperatures = [];


    const step = Math.max(1, Math.floor(data.length / maxPoints));

    for (let i = 0; i < data.length; i += step) {
        const item = data[i];
        if (item.timestamp && item.temperature !== undefined) {
            const time = new Date(item.timestamp);
            let timeStr;

            // 根据不同跨度动态格式化坐标轴
            if (currentHours <= 4)
                // 1-4小时：显示 时:分
                timeStr = time.getHours() + ':' + time.getMinutes().toString().padStart(2, '0');
            else if (currentHours <= 24)
                // 1天：显示 月/日 时:分
                timeStr = (time.getMonth() + 1) + '/' + time.getDate() + ' ' + time.getHours() + ':00';
            else
                // 1周：仅显示 月/日
                timeStr = (time.getMonth() + 1) + '/' + time.getDate();
            

            labels.push(timeStr);
            temperatures.push(item.temperature);
        }
    }

    if (currentHours >= 24) {
        temperatureChart.data.datasets[0].pointRadius = 0;
        temperatureChart.data.datasets[0].borderWidth = 1;
    } else {
        temperatureChart.data.datasets[0].pointRadius = 3;
        temperatureChart.data.datasets[0].borderWidth = 2;
    }

    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = temperatures;
    temperatureChart.update('none');
    document.getElementById('temperatureChart').style.opacity = '1';
}
