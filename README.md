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

### 一、在开发环境安装

#### 1. 环境要求
- Python 3.7+
- mosquitto MQTT代理

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 二、在服务器部署

1.给脚本执行权限并运行安装脚本：
```bash
chmod +x setup-ubuntu-env.sh
./setup-ubuntu-env.sh
```

3.启动系统：
```bash
./start.sh
```

4.停止系统：
```bash
./stop.sh
```

### 三、错误处理

1.安装python依赖时出错

给修复脚本执行权限并运行脚本：
```bash
chmod +x fix_deps.sh
./fix_deps.sh
```

2.安装并尝试运行mosquitto代理时出错

如果出现mosquitto僵死，占用端口，或者闪退，这多半是配置不当导致的。

给修复脚本执行权限并运行安装脚本：
```bash
chmod +x solve-mosquitto.sh
./solve-mosquitto.sh
```