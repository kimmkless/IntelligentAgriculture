#!/bin/bash
# stop.sh - Docker 停止脚本

echo "正在停止 IoT 传感器监控系统..."

# 停止并移除容器
docker-compose down

echo "✅ 服务已停止"