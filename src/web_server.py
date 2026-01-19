"""
Web服务器模块 - 提供Web界面和API
"""
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import logging
import threading
from functools import wraps
import secrets
import csv
from io import StringIO
from pathlib import Path

logger = logging.getLogger(__name__)

# 全局变量
db_instance = None
api_tokens = set()
socketio = SocketIO()


def create_app(db_instance_ref=None):
    """创建Flask应用"""
    global db_instance
    db_instance = db_instance_ref

    project_root = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        template_folder=str(project_root.joinpath("templates").resolve()),
        static_folder=str(project_root.joinpath("static").resolve())
    )
    print("Flask模板路径:", project_root / "templates")
    # 配置
    app.config['SECRET_KEY'] = secrets.token_hex(16)

    # 初始化扩展
    CORS(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # 注册路由
    register_routes(app)
    register_api_routes(app)

    return app


def register_routes(app):
    """注册Web页面路由"""

    @app.route('/')
    def index():
            return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
            return render_template('index.html')


def register_api_routes(app):
    """注册API路由"""

    # 认证装饰器
    def require_auth(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if auth_header:
                token = auth_header.replace('Bearer ', '')
                if token in api_tokens:
                    return f(*args, **kwargs)

            api_key = request.args.get('api_key')
            if api_key and api_key in api_tokens:
                return f(*args, **kwargs)

            return jsonify({'error': '未授权访问'}), 401

        return decorated_function

    # API路由
    @app.route('/api/devices', methods=['GET'])
    @require_auth
    def get_devices():
        """获取所有设备列表"""
        try:
            cursor = db_instance._get_connection().cursor()
            cursor.execute('''
                           SELECT d.*,
                                  COUNT(sd.data_id) as data_count,
                                  MAX(sd.timestamp) as latest_data_time
                           FROM devices d
                                    LEFT JOIN sensor_data sd ON d.device_id = sd.device_id
                           GROUP BY d.device_id
                           ORDER BY d.created_at DESC
                           ''')

            devices = []
            for row in cursor.fetchall():
                device = dict(row)
                # 处理时间字段
                if device.get('latest_data_time') and hasattr(device['latest_data_time'], 'isoformat'):
                    device['latest_data_time'] = device['latest_data_time'].isoformat()
                if device.get('created_at') and hasattr(device['created_at'], 'isoformat'):
                    device['created_at'] = device['created_at'].isoformat()
                if device.get('last_seen') and hasattr(device['last_seen'], 'isoformat'):
                    device['last_seen'] = device['last_seen'].isoformat()
                devices.append(device)

            return jsonify({'devices': devices, 'count': len(devices)})

        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/data/latest', methods=['GET'])
    def get_latest_data():
        """获取最新传感器数据"""
        try:
            device_id = request.args.get('device_id')
            limit = int(request.args.get('limit', 10))

            if device_id:
                data = db_instance.get_latest_sensor_data(device_id, limit)
            else:
                cursor = db_instance._get_connection().cursor()
                cursor.execute('''
                               SELECT *
                               FROM sensor_data
                               WHERE data_id IN (SELECT MAX(data_id)
                                                 FROM sensor_data
                                                 GROUP BY device_id)
                               ORDER BY timestamp DESC
                                   LIMIT ?
                               ''', (limit,))
                data = [dict(row) for row in cursor.fetchall()]

            # 格式化时间
            for item in data:
                if 'timestamp' in item and hasattr(item['timestamp'], 'isoformat'):
                    item['timestamp'] = item['timestamp'].isoformat()

            return jsonify({'data': data, 'count': len(data)})

        except Exception as e:
            logger.error(f"获取最新数据失败: {e}")
            return jsonify({'error': str(e)}), 500

    # 与图表相关的部分，可能有bug
    @app.route('/api/data/history', methods=['GET'])
    def get_history_data():
        try:
            device_id = request.args.get('device_id', 'SmartAgriculture_thermometer')
            # 1. 确保 hours 转换正确
            try:
                hours_val = float(request.args.get('hours', 1))
            except:
                hours_val = 1.0

            # 2. 统一时间格式：强制使用带有空格的 SQL 标准格式
            now = datetime.now()
            start_time_dt = now - timedelta(hours=hours_val)
            
            # 修复关键点：使用 strftime 而不是 isoformat()
            start_time_str = start_time_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"正在查询设备 {device_id} 从 {start_time_str} 开始的数据")

            cursor = db_instance._get_connection().cursor()

            # 3. 针对不同跨度使用不同的 SQL (适配 SQLite)
            if hours_val <= 1:
                # 1小时：查原始数据
                sql = "SELECT timestamp, temperature, humidity FROM sensor_data WHERE device_id = ? AND timestamp >= ? ORDER BY timestamp ASC"
            else:
                # 4小时/1天/1周：使用聚合
                # 计算聚合步长（秒）：1小时内显示不聚合，4小时每5分(300s)，1天每15分(900s)，1周每2小时(7200s)
                interval = 900 # 默认 15 分钟
                if hours_val > 24: interval = 7200
                elif hours_val <= 4: interval = 300

                # 使用 datetime(..., 'localtime') 确保聚合后的时间戳与本地时间一致
                sql = f'''
                    SELECT 
                        datetime((strftime('%s', timestamp) / {interval}) * {interval}, 'unixepoch', 'localtime') as timestamp, 
                        AVG(temperature) as temperature, 
                        AVG(humidity) as humidity
                    FROM sensor_data 
                    WHERE device_id = ? AND timestamp >= ? 
                    GROUP BY (strftime('%s', timestamp) / {interval})
                    ORDER BY timestamp ASC
                '''

            cursor.execute(sql, (device_id, start_time_str))
            rows = cursor.fetchall()
            
            # 4. 转换结果
            data = [dict(row) for row in rows]
            
            return jsonify({
                'status': 'success',
                'data': data,
                'count': len(data),
                'debug': {'start_time_used': start_time_str}
            })

        except Exception as e:
            logger.error(f"历史数据查询失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/statistics/device/<device_id>', methods=['GET'])
    def get_device_statistics(device_id):
        """获取设备统计信息"""
        try:
            stats = db_instance.get_device_statistics(device_id)

            stats_dict = dict(stats)

            # 格式化时间字段
            for time_field in ['first_record', 'last_record', 'last_seen']:
                value = stats_dict.get(time_field)
            if value:
                # 修复处：只有当它是 datetime 对象时才调用 isoformat()
                if hasattr(value, 'isoformat'):
                    stats_dict[time_field] = value.isoformat()
                else:
                    # 如果已经是字符串，确保它是干净的字符串
                    stats_dict[time_field] = str(value)

            return jsonify(stats)

        except Exception as e:
            logger.error(f"获取设备统计失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/system/status', methods=['GET'])
    def get_system_status():
        """获取系统状态"""
        try:
            cursor = db_instance._get_connection().cursor()

            # 获取设备统计
            cursor.execute('''
                           SELECT COUNT(*)                                       as total_count,
                                  SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count
                           FROM devices
                           ''')
            row = cursor.fetchone()
        
            # 强制转换为 int，防止 jsonify 失败
            total_devices = int(row['total_count']) if row['total_count'] is not None else 0
            active_devices = int(row['active_count']) if row['active_count'] is not None else 0

            # 获取今日数据量
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            cursor.execute('''
                           SELECT COUNT(*) as today_readings
                           FROM sensor_data
                           WHERE timestamp >= ?
                           ''', (today_start.isoformat(),))
            today_data = cursor.fetchone()[0]

            status = {
                'system': 'running',
                'database': 'connected',
                'timestamp': datetime.now().isoformat(),
                'total_devices': total_devices,
                'active_devices': active_devices,
                'today_readings': today_data
            }

            return jsonify(status)

        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return jsonify({'error': str(e), 'system': 'error'}), 500

    @app.route('/api/export/csv', methods=['GET'])
    @require_auth
    def export_csv():
        """导出数据为CSV格式"""
        try:
            device_id = request.args.get('device_id')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time', datetime.now().isoformat())

            cursor = db_instance._get_connection().cursor()

            query = '''
                    SELECT timestamp, device_id, temperature, humidity, noise, pm25, pm10, atmospheric_pressure, light_lux
                    FROM sensor_data
                    WHERE 1=1 \
                    '''
            params = []

            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            query += " AND timestamp <= ? ORDER BY timestamp DESC"
            params.append(end_time)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # 生成CSV
            output = StringIO()
            writer = csv.writer(output)

            # 写入表头
            writer.writerow(['时间', '设备ID', '温度(°C)', '湿度(%)', '噪声(dB)',
                             'PM2.5(μg/m³)', 'PM10(μg/m³)', '大气压(hPa)', '光照(lux)'])

            # 写入数据
            for row in rows:
                writer.writerow([
                    row['timestamp'].isoformat() if row['timestamp'] else '',
                    row['device_id'],
                    f"{row['temperature']:.1f}" if row['temperature'] is not None else '',
                    f"{row['humidity']:.1f}" if row['humidity'] is not None else '',
                    f"{row['noise']:.1f}" if row['noise'] is not None else '',
                    row['pm25'],
                    row['pm10'],
                    f"{row['atmospheric_pressure']:.1f}" if row['atmospheric_pressure'] is not None else '',
                    row['light_lux']
                ])

            return jsonify({
                'csv_data': output.getvalue(),
                'row_count': len(rows),
                'filename': f'sensor_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            })

        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/auth/token', methods=['POST'])
    def generate_token():
        """生成API访问令牌"""
        try:
            token = secrets.token_hex(32)
            api_tokens.add(token)

            return jsonify({
                'token': token,
                'expires_in': 3600,  # 1小时
                'created_at': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"生成令牌失败: {e}")
            return jsonify({'error': str(e)}), 500


# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    logger.info('客户端连接')
    socketio.emit('connected', {'message': '连接成功'})


@socketio.on('request_data')
def handle_request_data(data):
    """处理实时数据请求"""
    try:
        device_id = data.get('device_id')
        if device_id and db_instance:
            latest_data = db_instance.get_latest_sensor_data(device_id, 1)
            if latest_data:
                socketio.emit('sensor_data', latest_data[0])
    except Exception as e:
        logger.error(f"WebSocket数据处理失败: {e}")


def start_web_server(host='0.0.0.0', port=5000, debug=False, db_instance=None):
    """启动Web服务器"""
    # 创建Flask应用
    app = create_app(db_instance)

    # 生成默认API令牌
    default_token = secrets.token_hex(16)
    api_tokens.add(default_token)
    logger.info(f"默认API令牌: {default_token}")

    # 启动服务器
    if debug:
        socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
    else:
        from waitress import serve
        logger.info(f"Web服务器启动在: {host}:{port}")
        serve(app, host=host, port=port)
