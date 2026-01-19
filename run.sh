#!/bin/bash
# run.sh - Docker 启动脚本

echo "正在启动 IoT 传感器监控系统..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    echo "请先安装 Docker:"
    echo "Ubuntu/Debian: sudo apt-get install docker.io docker-compose"
    echo "CentOS/RHEL: sudo yum install docker docker-compose"
    exit 1
fi

# 创建必要目录
mkdir -p data logs config static templates

# 检查配置文件是否存在
if [ ! -f "config/mosquitto.conf" ]; then
    echo "创建默认 MQTT 配置文件..."
    mkdir -p config
    cp mosquitto.conf config/mosquitto.conf
fi

# 构建镜像
echo "正在构建 Docker 镜像..."
docker-compose build

# 启动服务
echo "正在启动服务..."
docker-compose up -d

# 显示状态
echo "等待服务启动..."
sleep 5

# 检查服务状态
docker-compose ps

echo ""
echo "✅ 服务启动完成！"
echo ""
echo "访问地址:"
echo "   本地: http://localhost:8080"
echo "   局域网: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "停止服务: ./stop.sh"
echo "查看日志: docker-compose logs -f"
echo ""