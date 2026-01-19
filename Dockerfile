# Dockerfile
FROM python:3.9-slim AS builder

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    mosquitto \
    mosquitto-clients \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/static /app/templates

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建非 root 用户
RUN useradd -m -u 1000 iotuser && \
    chown -R iotuser:iotuser /app

# 切换用户
USER iotuser

# 暴露端口
EXPOSE 8080 1883

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('127.0.0.1', 8080)); s.close()" || exit 1

# 启动命令
CMD ["python", "main.py"]