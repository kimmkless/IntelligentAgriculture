#!/usr/bin/env python3
"""
IoT传感器数据监控系统 - 主启动程序
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
    setup_logging()
    logger = logging.getLogger(__name__)

    print("""
    ╔══════════════════════════════════════════╗
    ║     IoT传感器数据监控系统 v1.0            ║
    ╚══════════════════════════════════════════╝
    """)

    # 检查依赖
    check_dependencies()

    # 获取本地IP
    local_ip = get_local_ip()

    # 初始化数据库
    logger.info("正在初始化数据库...")
    db = SensorDatabase()

    # 初始化MQTT处理器
    logger.info("正在初始化MQTT处理器...")
    mqtt_handler = MQTTHandler(db_instance=db)

    # 启动MQTT监听（在后台线程）
    logger.info("启动MQTT监听...")
    mqtt_handler.start_in_background()

    # 配置Web服务器
    config = {
        'host': '0.0.0.0',
        'port': 8080,
        'debug': False,
        'db_instance': db
    }

    print(f"""
    📊 系统信息:
       本地IP地址: {local_ip}
       Web端口: {config['port']}
       MQTT端口: 1883
       API接口: http://{local_ip}:{config['port']}/api/
       仪表板: http://{local_ip}:{config['port']}/

    🚀 服务正在启动...
    按 Ctrl+C 停止服务
    """)

    try:
        # 启动Web服务器（主线程）
        from src.web_server import start_web_server
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