// JavaScript主文件 - 添加实时运行时间功能
let temperatureChart = null;
let currentHours = 1;
let serverStartTime = null;
let uptimeUpdateInterval = null;

console.log("页面加载完成，开始初始化...");

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM加载完成，初始化图表...");
    initChart();
    loadChartData();

    // 每30秒刷新一次图表数据
    setInterval(loadChartData, 30000);

    // 初始加载系统数据
    loadSystemData();

    // 开始实时更新运行时间
    startRealTimeUptime();
});

// 初始化图表
function initChart() {
    console.log("初始化图表...");
    const ctx = document.getElementById('temperatureChart');

    if (!ctx) {
        console.error("找不到图表canvas元素！");
        return;
    }

    console.log("找到canvas元素，创建图表实例...");

    temperatureChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '温度 (°C)',
                data: [],
                borderColor: '#ff6b6b',
                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.1,
                pointRadius: 2
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
                    display: true,
                    title: {
                        display: true,
                        text: '数据点序列'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '温度 (°C)'
                    },
                    min: 0,
                    max: 50
                }
            }
        }
    });

    console.log("图表初始化完成");
}

// 启动实时运行时间更新
function startRealTimeUptime() {
    console.log("启动实时运行时间更新");

    // 每秒更新一次运行时间
    uptimeUpdateInterval = setInterval(updateRealTimeUptime, 1000);

    // 立即更新一次
    updateRealTimeUptime();
}

// 实时更新运行时间显示
function updateRealTimeUptime() {
    console.log("更新实时运行时间");

    // 如果还没有服务器启动时间，从系统数据中获取
    if (!serverStartTime) {
        const uptimeElement = document.getElementById('uptime');
        if (uptimeElement && uptimeElement.dataset.uptimeSeconds) {
            const uptimeSeconds = parseFloat(uptimeElement.dataset.uptimeSeconds);
            if (uptimeSeconds && !isNaN(uptimeSeconds)) {
                serverStartTime = new Date(Date.now() - (uptimeSeconds * 1000));
                console.log("从页面数据获取服务器启动时间:", serverStartTime);
            } else {
                // 如果还没有数据，等待下一次更新
                return;
            }
        } else {
            return;
        }
    }

    // 计算运行时间
    const now = new Date();
    const uptimeMs = now - serverStartTime;
    const uptimeSeconds = Math.floor(uptimeMs / 1000);

    // 格式化为天、小时、分钟、秒
    const days = Math.floor(uptimeSeconds / 86400);
    const hours = Math.floor((uptimeSeconds % 86400) / 3600);
    const minutes = Math.floor((uptimeSeconds % 3600) / 60);
    const seconds = uptimeSeconds % 60;

    // 构建显示字符串
    let uptimeStr = '';
    if (days > 0) {
        uptimeStr += `${days}天`;
    }
    if (hours > 0 || days > 0) {
        uptimeStr += `${hours}小时`;
    }
    if (minutes > 0 || hours > 0 || days > 0) {
        uptimeStr += `${minutes}分`;
    }
    uptimeStr += `${seconds}秒`;

    // 更新页面显示
    const uptimeElement = document.getElementById('uptime');
    if (uptimeElement) {
        uptimeElement.textContent = uptimeStr;
        uptimeElement.dataset.uptimeSeconds = uptimeSeconds;
    }
}

// 时间选择变化处理
function handleTimeChange() {
    console.log("时间选择改变:", currentHours);
    const selector = document.getElementById('timeRange');
    currentHours = parseFloat(selector.value);

    console.log("新的时间范围:", currentHours, "小时");

    // 显示加载状态
    showChartLoading();

    // 加载新数据
    loadChartData();
}

// 显示图表加载状态
function showChartLoading() {
    console.log("显示图表加载状态");
    const canvas = document.getElementById('temperatureChart');
    if (canvas) {
        canvas.style.opacity = '0.5';
    }

    const chartInfo = document.getElementById('chartInfo');
    if (chartInfo) {
        chartInfo.innerHTML = '正在加载数据...';
    }
}

// 隐藏图表加载状态
function hideChartLoading() {
    console.log("隐藏图表加载状态");
    const canvas = document.getElementById('temperatureChart');
    if (canvas) {
        canvas.style.opacity = '1';
    }
}

// 加载图表数据
function loadChartData() {
    console.log(`加载图表数据: ${currentHours}小时`);

    const url = `/api/data/history?device_id=SmartAgriculture_thermometer&hours=${currentHours}`;
    console.log("请求URL:", url);

    showChartLoading();

    fetch(url)
        .then(response => {
            console.log("收到响应，状态:", response.status);
            if (!response.ok) {
                throw new Error(`HTTP错误 ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("收到图表数据:", data);

            if (data.status === 'success' && data.data && data.data.length > 0) {
                console.log(`数据点数量: ${data.data.length}`);
                updateChart(data.data);
            } else {
                console.log("没有数据或状态不是success:", data);
                showNoDataMessage();
            }
        })
        .catch(error => {
            console.error("加载图表数据失败:", error);
            showNoDataMessage();
        });
}

// 用数据更新图表
function updateChart(data) {
    console.log("更新图表，数据:", data);

    if (!temperatureChart) {
        console.error("图表未初始化！");
        return;
    }

    console.log(`数据点数量: ${data.length}`);

    // 准备图表数据
    const labels = [];
    const temperatureValues = [];

    // 取前100个点显示，避免图表过于拥挤
    const displayCount = Math.min(data.length, 100);
    const step = Math.ceil(data.length / displayCount);

    for (let i = 0; i < data.length; i += step) {
        const item = data[i];
        if (item && item.temperature !== undefined) {
            labels.push(`点${labels.length + 1}`);
            temperatureValues.push(item.temperature);
        }
    }

    console.log(`显示 ${labels.length} 个数据点`);

    // 更新图表数据
    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = temperatureValues;

    // 动态调整Y轴范围
    if (temperatureValues.length > 0) {
        const minTemp = Math.min(...temperatureValues);
        const maxTemp = Math.max(...temperatureValues);
        const padding = 2;

        temperatureChart.options.scales.y.min = Math.max(0, minTemp - padding);
        temperatureChart.options.scales.y.max = Math.min(50, maxTemp + padding);

        console.log(`温度范围: ${minTemp.toFixed(1)} - ${maxTemp.toFixed(1)}°C`);
    }

    // 更新图表
    temperatureChart.update();
    hideChartLoading();

    // 更新图表信息显示
    updateChartInfo(data.length, labels.length);

    console.log("图表更新完成");
}

// 更新图表信息显示
function updateChartInfo(totalPoints, displayPoints) {
    const chartInfo = document.getElementById('chartInfo');
    if (chartInfo) {
        if (totalPoints > displayPoints) {
            chartInfo.innerHTML = `显示 ${displayPoints} 个聚合点 (共 ${totalPoints} 个数据点)`;
        } else {
            chartInfo.innerHTML = `显示 ${totalPoints} 个数据点`;
        }
        console.log("图表信息:", chartInfo.innerHTML);
    }
}

// 显示无数据消息
function showNoDataMessage() {
    console.log("显示无数据消息");

    if (!temperatureChart) {
        console.error("图表未初始化！");
        return;
    }

    // 清空图表
    temperatureChart.data.labels = ['无数据'];
    temperatureChart.data.datasets[0].data = [0];

    // 设置Y轴范围为0-1
    temperatureChart.options.scales.y.min = 0;
    temperatureChart.options.scales.y.max = 1;

    temperatureChart.update();
    hideChartLoading();

    // 更新图表信息
    const chartInfo = document.getElementById('chartInfo');
    if (chartInfo) {
        chartInfo.innerHTML = '暂无图表数据';
    }

    console.log("无数据消息已显示");
}

// 加载系统数据
function loadSystemData() {
    console.log("加载系统数据...");

    fetch('/api/system/status')
        .then(response => response.json())
        .then(data => {
            console.log("系统状态数据:", data);

            // 更新系统概览
            updateSystemOverview(data);

            // 保存服务器启动时间用于实时计算
            if (data.server_start_time) {
                serverStartTime = new Date(data.server_start_time);
                console.log("从API获取服务器启动时间:", serverStartTime);

                // 更新运行时间显示
                updateRealTimeUptime();
            }

            // 更新最新传感器数据
            loadLatestSensorData();
        })
        .catch(error => {
            console.error("加载系统数据失败:", error);
        });
}

// 更新系统概览
function updateSystemOverview(data) {
    console.log("更新系统概览:", data);

    if (data.active_devices !== undefined) {
        document.getElementById('onlineDevices').textContent = data.active_devices;
    }
    if (data.today_readings !== undefined) {
        document.getElementById('todayData').textContent = `${data.today_readings} 条`;
    }

    // 保存uptime_seconds到data属性，用于实时计算
    if (data.uptime_seconds !== undefined) {
        const uptimeElement = document.getElementById('uptime');
        if (uptimeElement) {
            uptimeElement.dataset.uptimeSeconds = data.uptime_seconds;
        }
    }

    if (data.mqtt_status) {
        document.getElementById('mqttStatus').textContent = data.mqtt_status;
        const mqttElement = document.getElementById('mqttStatus');
        if (data.mqtt_status === '在线') {
            mqttElement.style.color = '#48bb78';
        } else {
            mqttElement.style.color = '#f56565';
        }
    }
    if (data.data_integrity !== undefined) {
        document.getElementById('dataIntegrity').textContent = `${data.data_integrity.toFixed(1)}%`;
        const integrityElement = document.getElementById('dataIntegrity');
        if (data.data_integrity >= 80) {
            integrityElement.style.color = '#48bb78';
        } else if (data.data_integrity >= 50) {
            integrityElement.style.color = '#ed8936';
        } else {
            integrityElement.style.color = '#f56565';
        }
    }
    if (data.data_quality !== undefined) {
        document.getElementById('dataQuality').textContent = `${data.data_quality.toFixed(1)}%`;
        const qualityElement = document.getElementById('dataQuality');
        if (data.data_quality >= 90) {
            qualityElement.style.color = '#48bb78';
        } else if (data.data_quality >= 70) {
            qualityElement.style.color = '#ed8936';
        } else {
            qualityElement.style.color = '#f56565';
        }
    }
}

// 加载最新传感器数据
function loadLatestSensorData() {
    console.log("加载最新传感器数据...");

    fetch('/api/data/latest?limit=5')
        .then(response => response.json())
        .then(data => {
            console.log("最新传感器数据:", data);

            if (data.data && data.data.length > 0) {
                updateEnvironmentData(data.data[0]);
                updateDataTable(data.data);
            }
        })
        .catch(error => {
            console.error("加载传感器数据失败:", error);
        });
}

// 更新环境数据
function updateEnvironmentData(latest) {
    console.log("更新环境数据:", latest);

    document.getElementById('temperature').textContent =
        `${latest.temperature ? latest.temperature.toFixed(1) : '--'} °C`;
    document.getElementById('humidity').textContent =
        `${latest.humidity ? latest.humidity.toFixed(1) : '--'} %`;
    document.getElementById('pm25').textContent =
        `${latest.pm25 || '--'} μg/m³`;
    document.getElementById('light').textContent =
        `${latest.light_lux || '--'} lux`;
}

// 更新数据表格
function updateDataTable(data) {
    console.log("更新数据表格，数据:", data);

    const tbody = document.getElementById('dataTableBody');
    if (!tbody) {
        console.error("找不到数据表格tbody元素！");
        return;
    }

    tbody.innerHTML = '';

    data.forEach((item, index) => {
        const row = document.createElement('tr');

        // 格式化时间
        let timeStr = '--';
        if (item.timestamp) {
            try {
                // 尝试解析时间
                const date = new Date(item.timestamp);
                if (!isNaN(date.getTime())) {
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    const seconds = String(date.getSeconds()).padStart(2, '0');
                    timeStr = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
                } else {
                    timeStr = item.timestamp;
                }
            } catch (e) {
                timeStr = item.timestamp;
            }
        }

        row.innerHTML = `
            <td>${timeStr}</td>
            <td>${item.device_id || 'SmartAgriculture_thermometer'}</td>
            <td>${item.temperature ? item.temperature.toFixed(1) : '--'}</td>
            <td>${item.humidity ? item.humidity.toFixed(1) : '--'}</td>
            <td>${item.pm25 || '--'}</td>
            <td>${item.light_lux || '--'}</td>
        `;
        tbody.appendChild(row);
    });

    console.log("数据表格更新完成");
}

// 刷新数据函数
function refreshData() {
    console.log("手动刷新数据");
    loadChartData();
    loadSystemData();
    loadLatestSensorData();
}

// 页面卸载时清理定时器
window.addEventListener('beforeunload', function() {
    if (uptimeUpdateInterval) {
        clearInterval(uptimeUpdateInterval);
        console.log("清理运行时间更新定时器");
    }
});