"""
工具函数模块
包含日志设置、依赖检查、IP获取等通用功能
"""
import logging
import sys
import subprocess
import socket
import platform
import importlib
from pathlib import Path
from typing import List, Dict, Any


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为None则只输出到控制台
    """
    # 创建日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 配置基础日志
    handlers = []

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)

    # 配置根日志器
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers
    )

    # 设置特定库的日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlite3').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"日志系统初始化完成，级别: {log_level}")

    if log_file:
        logger.info(f"日志文件: {log_file}")


def check_dependencies():
    """
    检查项目依赖是否已安装
    """
    required_packages = [
        'flask',
        'flask_cors',
        'flask_socketio',
        'paho.mqtt',
        'waitress'
    ]

    missing_packages = []

    print("🔍 检查项目依赖...")

    for package in required_packages:
        try:
            # 转换包名（有些包的导入名不同）
            import_name = package.replace('-', '_').replace(' ', '_')
            importlib.import_module(import_name)
            print(f"  ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package}")

    if missing_packages:
        print("\n⚠️  缺少以下依赖包:")
        for package in missing_packages:
            print(f"    - {package}")

        print("\n请使用以下命令安装:")
        print("pip install -r requirements.txt")
        print("\n或者单独安装:")
        print(f"pip install {' '.join(missing_packages)}")

        response = input("\n是否现在安装？(y/n): ").lower()
        if response == 'y':
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
                print("✅ 依赖安装完成，请重新运行程序")
                sys.exit(0)
            except subprocess.CalledProcessError as e:
                print(f"❌ 安装失败: {e}")
                sys.exit(1)
        else:
            print("❌ 缺少必要依赖，程序无法运行")
            sys.exit(1)

    print("✅ 所有依赖检查通过")


def get_local_ip() -> str:
    """
    获取本机在局域网中的IP地址

    Returns:
        IP地址字符串
    """
    try:
        # 尝试通过连接到外部服务器获取IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)

        try:
            # 连接到谷歌DNS，但不会发送数据
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except (socket.error, socket.timeout):
            # 如果上述方法失败，尝试获取主机名对应的IP
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
            except socket.error:
                ip = "127.0.0.1"
        finally:
            s.close()

        return ip
    except Exception as e:
        logging.getLogger(__name__).warning(f"获取本地IP失败: {e}")
        return "127.0.0.1"


def check_mqtt_broker_installed() -> bool:
    """
    检查MQTT代理（mosquitto）是否已安装

    Returns:
        True如果已安装，False如果未安装
    """
    system = platform.system()

    try:
        if system == "Windows":
            # Windows上检查mosquitto命令
            result = subprocess.run(
                ["where", "mosquitto"],
                capture_output=True,
                text=True,
                shell=True
            )
            return result.returncode == 0
        elif system in ["Linux", "Darwin"]:
            # Linux和macOS上检查mosquitto命令
            result = subprocess.run(
                ["which", "mosquitto"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        else:
            return False
    except Exception:
        return False


def get_system_info() -> Dict[str, Any]:
    """
    获取系统信息

    Returns:
        包含系统信息的字典
    """
    return {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'python_version': platform.python_version(),
        'processor': platform.processor(),
        'machine': platform.machine(),
        'node': platform.node()
    }


def create_project_structure():
    """
    创建项目目录结构
    """
    project_root = Path(__file__).parent.parent
    directories = [
        'templates',
        'static/css',
        'static/js',
        'static/images',
        'data',
        'logs'
    ]

    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)

    # 创建默认的HTML文件
    templates_dir = project_root / 'templates'
    if not (templates_dir / 'index.html').exists():
        # 创建简单的index.html文件
        index_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT监控系统</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .status {
            display: inline-block;
            padding: 5px 10px;
            background: #48bb78;
            color: white;
            border-radius: 5px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌱 IoT传感器数据监控系统</h1>
        <p>实时监控农业环境传感器数据</p>
        <span class="status">系统运行中</span>
    </div>

    <div class="card">
        <h2>系统信息</h2>
        <p>Web服务器正在运行！</p>
        <p>API接口:</p>
        <ul>
            <li><a href="/api/status">系统状态</a></li>
            <li><a href="/api/devices">设备列表</a></li>
            <li><a href="/api/data/latest">最新数据</a></li>
        </ul>
    </div>

    <div class="card">
        <h2>MQTT连接信息</h2>
        <p>等待ESP32设备连接...</p>
    </div>
</body>
</html>
"""
        with open(templates_dir / 'index.html', 'w', encoding='utf-8') as f:
            f.write(index_content)

    return project_root


def format_timestamp(timestamp, format_str: str = "%Y-%m-%d %H:%M:%S"):
    """
    格式化时间戳

    Args:
        timestamp: 时间戳，可以是datetime对象或字符串
        format_str: 格式字符串

    Returns:
        格式化后的时间字符串
    """
    from datetime import datetime

    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp
    elif hasattr(timestamp, 'strftime'):
        dt = timestamp
    else:
        return str(timestamp)

    return dt.strftime(format_str)


def human_readable_size(size_bytes: int) -> str:
    """
    将字节大小转换为人类可读的格式

    Args:
        size_bytes: 字节大小

    Returns:
        人类可读的大小字符串
    """
    if size_bytes == 0:
        return "0B"

    units = ["B", "KB", "MB", "GB", "TB"]
    import math

    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {units[i]}"


def validate_ip_address(ip: str) -> bool:
    """
    验证IP地址格式

    Args:
        ip: IP地址字符串

    Returns:
        True如果是有效的IP地址
    """
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def is_port_in_use(port: int) -> bool:
    """
    检查端口是否被占用

    Args:
        port: 端口号

    Returns:
        True如果端口已被占用
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def get_available_port(start_port: int = 8000) -> int:
    """
    获取可用的端口号

    Args:
        start_port: 起始端口号

    Returns:
        可用的端口号
    """
    port = start_port
    while is_port_in_use(port):
        port += 1

    return port