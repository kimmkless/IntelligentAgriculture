# IoT传感器数据监控系统

## 项目概述
这是一个基于Flask的IoT传感器数据监控系统，用于接收、存储和展示从ESP32设备收集的传感器数据。系统包括MQTT数据接收、数据存储、Web展示和API接口功能。

## 功能特性
- ✅ 实时接收MQTT传感器数据
- ✅ SQLite数据存储
- ✅ 实时Web仪表板
- ✅ RESTful API接口
- ✅ 数据导出功能
- ✅ 自动启动MQTT代理
- ✅ 响应式Web界面

## 安装说明

### 1. 环境要求
- Python 3.7+
- mosquitto MQTT代理

### 2. 安装依赖
```bash
pip install -r requirements.txt