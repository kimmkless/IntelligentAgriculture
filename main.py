#!/usr/bin/env python3
"""
IoT传感器数据监控系统 - Docker 优化版本
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.web_server import start_web_server
from src.mqtt_handler import MQTTHandler
from src.database import SensorDatabase
from src.utils import setup_logging, check_dependencies, get_local_ip


def main():
    """主函数"""
    # 读取环境变量
    web_host = os.getenv('WEB_HOST', '0.0.0.0')
    web_port = int(os.getenv('WEB_PORT', '8080'))
    mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'

    # 设置日志
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_level=log_level, log_file='logs/app.log')
    logger = logging.getLogger(__name__)

    print(f"""
    ╔═══════════════════════════════════════════════════════╗
    ║     IoT传感器数据监控系统 v1.0 (Docker)               ║
    ╚═══════════════════════════════════════════════════════╝

    配置信息:
        Web服务: {web_host}:{web_port}
        MQTT代理: {mqtt_broker}:{mqtt_port}
        调试模式: {debug_mode}
        日志级别: {log_level}
    """)

    # 检查依赖
    check_dependencies()

    # 获取本地IP
    local_ip = get_local_ip()

    # 初始化数据库
    logger.info("正在初始化数据库...")
    db_path = os.getenv('DB_PATH', 'data/iot_sensor_data.db')
    db = SensorDatabase(db_path)

    # 初始化MQTT处理器
    logger.info(f"正在初始化MQTT处理器，代理: {mqtt_broker}:{mqtt_port}...")
    mqtt_handler = MQTTHandler(broker_ip=mqtt_broker, port=mqtt_port, db_instance=db)

    # 启动MQTT监听（在后台线程）
    logger.info("启动MQTT监听...")
    mqtt_handler.start_in_background()

    # 配置Web服务器
    config = {
        'host': web_host,
        'port': web_port,
        'debug': debug_mode,
        'db_instance': db
    }

    print(f"""
    📊 系统信息:
       本地IP地址: {local_ip}
       Web端口: {web_port}
       MQTT端口: {mqtt_port}
       API接口: http://localhost:{web_port}/api/
       仪表板: http://localhost:{web_port}/

       访问地址:
       局域网: http://{local_ip}:{web_port}/
       本机: http://localhost:{web_port}/

    🚀 服务正在启动...
    按 Ctrl+C 停止服务
    """)

    try:
        # 启动Web服务器（主线程）
        start_web_server(**config)
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {e}", exc_info=True)
    finally:
        # 清理资源
        logger.info("正在关闭数据库连接...")
        db.close()
        logger.info("正在停止MQTT处理器...")
        mqtt_handler.stop()
        logger.info("服务已安全停止")


if __name__ == "__main__":
    main()