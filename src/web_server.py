"""
Web服务器模块 - 提供Web界面和API
"""
import os

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
server_start_time = None
mqtt_handler = None


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
        # --- 新增的照片读取逻辑开始 ---
        # 1. 定义照片文件夹路径
        photos_path = os.path.join(app.static_folder, 'photos')

        # 2. 获取该目录下所有图片文件
        photo_files = []
        if os.path.exists(photos_path):
            try:
                all_files = os.listdir(photos_path)
                # 只保留 jpg, jpeg, png, gif, bmp 等格式
                photo_files = [
                    f for f in all_files
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
                ]
                photo_files.sort()  # 排序，保证展示顺序固定
            except Exception as e:
                logger.error(f"读取照片目录失败: {e}")

        # --- 新增的照片读取逻辑结束 ---

        # 3. 将 photo_files 传递给模板
        return render_template('index.html', photos=photo_files)

    @app.route('/dashboard')
    def dashboard():
            return index()


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

    # 与图表相关的部分
    # 替换 get_history_data 函数
    @app.route('/api/data/history', methods=['GET'])
    def get_history_data():
        """获取历史数据用于图表 - 修复版本"""
        try:
            from datetime import datetime, timedelta

            device_id = request.args.get('device_id', 'SmartAgriculture_thermometer')

            # 1. 解析时间范围参数
            time_range = request.args.get('hours', '1')
            try:
                hours = float(time_range)
            except ValueError:
                hours = 1.0

            # 限制最小为0.1小时，最大为720小时（30天）
            hours = max(0.1, min(hours, 720))

            logger.info(f"查询图表数据: 设备={device_id}, 时间范围={hours}小时")

            cursor = db_instance._get_connection().cursor()

            # 2. 首先获取数据库中的最新时间戳
            cursor.execute('''
                SELECT MAX(timestamp) as latest_time 
                FROM sensor_data 
                WHERE device_id = ?
            ''', (device_id,))

            latest_time_row = cursor.fetchone()
            latest_time_str = latest_time_row['latest_time'] if latest_time_row and latest_time_row[
                'latest_time'] else None

            if not latest_time_str:
                # 没有数据
                logger.warning(f"设备 {device_id} 没有数据")
                return jsonify({
                    'status': 'success',
                    'data': [],
                    'count': 0,
                    'message': '设备暂无数据'
                })

            # 3. 将数据库中的最新时间转换为datetime对象
            # 尝试解析时间格式
            latest_time = None
            time_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y/%m/%d %H:%M:%S'
            ]

            for fmt in time_formats:
                try:
                    latest_time = datetime.strptime(latest_time_str, fmt)
                    break
                except ValueError:
                    continue

            if not latest_time:
                # 无法解析时间，使用当前时间
                latest_time = datetime.now()
                logger.warning(f"无法解析时间格式: {latest_time_str}, 使用当前时间")

            # 4. 计算开始时间（相对于数据库中的最新时间）
            start_time = latest_time - timedelta(hours=hours)
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')

            logger.info(f"使用数据库最新时间: {latest_time_str}, 查询开始时间: {start_time_str}")

            # 5. 查询数据（不聚合，直接获取原始数据）
            # 使用字符串比较，因为数据库中的时间是字符串
            cursor.execute('''
                SELECT timestamp, temperature, humidity
                FROM sensor_data 
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (device_id, start_time_str))

            rows = cursor.fetchall()

            # 6. 处理查询结果
            data = []
            for row in rows:
                if row['temperature'] is not None:
                    # 确保时间戳是字符串格式
                    timestamp = row['timestamp']
                    if hasattr(timestamp, 'isoformat'):
                        timestamp = timestamp.isoformat()
                    elif not isinstance(timestamp, str):
                        timestamp = str(timestamp)

                    data.append({
                        'timestamp': timestamp,
                        'temperature': float(row['temperature']),
                        'humidity': float(row['humidity']) if row['humidity'] is not None else None
                    })

            logger.info(f"查询完成，返回 {len(data)} 个数据点")

            # 7. 如果数据点太多，进行前端聚合
            # 这里只是设置一个标志，让前端知道需要聚合
            needs_aggregation = len(data) > 100

            return jsonify({
                'status': 'success',
                'data': data,
                'count': len(data),
                'needs_aggregation': needs_aggregation,
                'debug': {
                    'time_range_hours': hours,
                    'start_time': start_time_str,
                    'latest_time': latest_time_str,
                    'data_points': len(data),
                    'query_mode': 'direct_query'
                }
            })

        except Exception as e:
            logger.error(f"历史数据查询失败: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'error': str(e),
                'data': []
            }), 500

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
            from datetime import datetime, timedelta

            cursor = db_instance._get_connection().cursor()

            # 获取设备统计
            cursor.execute('''
                SELECT COUNT(*) as total_count,
                       SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count
                FROM devices
            ''')
            row = cursor.fetchone()

            # 强制转换为 int，防止 jsonify 失败
            total_devices = int(row['total_count']) if row['total_count'] is not None else 0
            active_devices = int(row['active_count']) if row['active_count'] is not None else 0

            # 获取今日数据量（修正：使用本地日期的开始时间）
            now = datetime.now()
            today_start = datetime(now.year, now.month, now.day, 0, 0, 0)

            cursor.execute('''
                SELECT COUNT(*) as today_readings
                FROM sensor_data
                WHERE timestamp >= ?
            ''', (today_start.isoformat(),))
            today_row = cursor.fetchone()
            today_data = int(today_row[0]) if today_row and today_row[0] is not None else 0

            # 计算系统运行时间
            uptime_str = "0天0小时0分0秒"
            uptime_seconds = 0

            if server_start_time:
                uptime_delta = datetime.now() - server_start_time
                uptime_seconds = uptime_delta.total_seconds()
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                uptime_str = f"{days}天{hours}小时{minutes}分{seconds}秒"

            # 获取MQTT状态
            mqtt_status = "离线"
            mqtt_stability = "--"
            if mqtt_handler:
                try:
                    mqtt_info = mqtt_handler.get_connection_status()
                    mqtt_status = "在线" if mqtt_info.get('connected', False) else "离线"
                    mqtt_stability = mqtt_info.get('stability', '--')
                except Exception as e:
                    logger.error(f"获取MQTT状态失败: {e}")
                    mqtt_status = "未知"

            # 计算数据完整性（基于所有数据）
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN temperature IS NOT NULL THEN 1 ELSE 0 END) as temp_count,
                    SUM(CASE WHEN humidity IS NOT NULL THEN 1 ELSE 0 END) as hum_count,
                    SUM(CASE WHEN pm25 IS NOT NULL THEN 1 ELSE 0 END) as pm25_count,
                    SUM(CASE WHEN light_lux IS NOT NULL THEN 1 ELSE 0 END) as light_count
                FROM sensor_data
            ''')
            integrity_row = cursor.fetchone()

            data_integrity = 0
            if integrity_row and integrity_row['total'] > 0:
                total_records = integrity_row['total']
                # 检查4个关键字段的完整性
                field_checks = []
                for field, count in [('temperature', integrity_row['temp_count']),
                                     ('humidity', integrity_row['hum_count']),
                                     ('pm25', integrity_row['pm25_count']),
                                     ('light', integrity_row['light_count'])]:
                    field_completeness = (count / total_records) * 100
                    field_checks.append(field_completeness)

                # 计算平均完整性
                data_integrity = sum(field_checks) / len(field_checks) if field_checks else 0
            else:
                data_integrity = 0

            # 计算数据质量（基于最近24小时数据）
            one_day_ago = datetime.now() - timedelta(days=1)
            one_day_ago_str = one_day_ago.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN temperature IS NOT NULL AND temperature BETWEEN -20 AND 60 THEN 1 ELSE 0 END) as valid_temp,
                    SUM(CASE WHEN humidity IS NOT NULL AND humidity BETWEEN 0 AND 100 THEN 1 ELSE 0 END) as valid_hum,
                    SUM(CASE WHEN pm25 IS NOT NULL AND pm25 BETWEEN 0 AND 1000 THEN 1 ELSE 0 END) as valid_pm25,
                    SUM(CASE WHEN light_lux IS NOT NULL AND light_lux BETWEEN 0 AND 100000 THEN 1 ELSE 0 END) as valid_light
                FROM sensor_data 
                WHERE timestamp >= ?
            ''', (one_day_ago_str,))

            quality_row = cursor.fetchone()

            data_quality = 0
            if quality_row and quality_row['total'] > 0:
                total_records = quality_row['total']
                # 计算每个字段的质量分数
                quality_scores = []

                # 温度质量（-20到60度合理范围）
                if quality_row['valid_temp'] is not None:
                    temp_quality = (quality_row['valid_temp'] / total_records) * 100
                    quality_scores.append(temp_quality)

                # 湿度质量（0-100%合理范围）
                if quality_row['valid_hum'] is not None:
                    hum_quality = (quality_row['valid_hum'] / total_records) * 100
                    quality_scores.append(hum_quality)

                # PM2.5质量（0-1000合理范围）
                if quality_row['valid_pm25'] is not None:
                    pm25_quality = (quality_row['valid_pm25'] / total_records) * 100
                    quality_scores.append(pm25_quality)

                # 光照质量（0-100000 lux合理范围）
                if quality_row['valid_light'] is not None:
                    light_quality = (quality_row['valid_light'] / total_records) * 100
                    quality_scores.append(light_quality)

                # 计算平均质量分数
                if quality_scores:
                    data_quality = sum(quality_scores) / len(quality_scores)
                else:
                    data_quality = 0
            else:
                data_quality = 0

            # 获取最新的数据更新时间
            cursor.execute('''
                SELECT MAX(timestamp) as last_update
                FROM sensor_data
            ''')
            last_update_row = cursor.fetchone()
            last_update = None

            if last_update_row and last_update_row['last_update']:
                last_update_value = last_update_row['last_update']
                # 处理不同的时间格式
                if isinstance(last_update_value, datetime):
                    last_update = last_update_value.isoformat()
                elif isinstance(last_update_value, str):
                    # 如果是字符串，直接使用
                    last_update = last_update_value
                    # 尝试解析并重新格式化为标准格式
                    try:
                        # 尝试解析常见的时间格式
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                            try:
                                dt = datetime.strptime(last_update_value, fmt)
                                last_update = dt.isoformat()
                                break
                            except ValueError:
                                continue
                    except Exception as e:
                        logger.warning(f"时间格式解析失败: {last_update_value}, 错误: {e}")
                else:
                    last_update = str(last_update_value)

            status = {
                'system': 'running',
                'database': 'connected',
                'timestamp': datetime.now().isoformat(),
                'last_update': last_update,
                'total_devices': total_devices,
                'active_devices': active_devices,
                'today_readings': today_data,
                'uptime_seconds': uptime_seconds,  # 确保有这个字段
                'uptime_str': uptime_str,  # 保留这个字段用于初始显示
                'mqtt_status': mqtt_status,
                'mqtt_stability': mqtt_stability,
                'data_integrity': round(data_integrity, 1),
                'data_quality': round(data_quality, 1),
                'server_start_time': server_start_time.isoformat() if server_start_time else None  # 确保有这个字段
            }

            logger.debug(f"系统状态: {status}")
            return jsonify(status)

        except Exception as e:
            logger.error(f"获取系统状态失败: {e}", exc_info=True)
            return jsonify({
                'error': str(e),
                'system': 'error',
                'today_readings': 0,
                'uptime_str': '0天0小时0分0秒',
                'data_integrity': 0,
                'data_quality': 0
            }), 500

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
