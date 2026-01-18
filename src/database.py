"""
数据库操作模块 - 基于原sensor_database.py
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
import queue

logger = logging.getLogger(__name__)

class SensorDatabase:
    """传感器数据库管理类 - 线程安全的版本"""

    def __init__(self, db_path: str = None):
        """初始化数据库连接"""
        if db_path is None:
            # 默认使用项目根目录下的data文件夹
            db_path = Path(__file__).parent.parent / "data" / "iot_sensor_data.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self._local = threading.local()  # 线程局部存储
        self._init_database()

    def _get_connection(self):
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 创建设备信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT,
                    device_type TEXT,
                    client_id TEXT,
                    username TEXT,
                    service_id TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # 创建传感器数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    crop_area_id INTEGER DEFAULT 1,
                    temperature REAL,
                    humidity REAL,
                    noise REAL,
                    pm25 INTEGER,
                    pm10 INTEGER,
                    atmospheric_pressure REAL,
                    light_lux INTEGER,
                    soil_temperature REAL,
                    soil_humidity REAL,
                    soil_conductivity REAL,
                    raw_json TEXT,
                    FOREIGN KEY (device_id) REFERENCES devices (device_id)
                )
            ''')

            # 创建设备状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_status (
                    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    wifi_strength INTEGER,
                    battery_level REAL,
                    uptime_seconds INTEGER,
                    last_error TEXT,
                    is_online BOOLEAN,
                    FOREIGN KEY (device_id) REFERENCES devices (device_id)
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensor_data_device_time 
                ON sensor_data(device_id, timestamp)
            ''')

            conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")

            # 插入示例数据
            self._insert_sample_data()

        except sqlite3.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def _insert_sample_data(self):
        """插入示例设备数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 检查是否已存在示例设备
            cursor.execute(
                "SELECT COUNT(*) FROM devices WHERE device_id = ?",
                ("SmartAgriculture_thermometer",)
            )

            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO devices (
                        device_id, device_name, device_type, client_id,
                        username, service_id, location, last_seen, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    "SmartAgriculture_thermometer",
                    "农业温度监测设备",
                    "ESP32_RS485_Sensor",
                    "SmartAgriculture_thermometer_0_0_2025071810",
                    "SmartAgriculture_thermometer",
                    "ESP32_TH",
                    "实验农田A区",
                    datetime.now().isoformat(),
                    1
                ))
                conn.commit()
                logger.info("示例设备数据插入完成")

        except sqlite3.Error as e:
            logger.error(f"插入示例数据失败: {e}")

    def store_sensor_data(self, device_id: str, data: Dict[str, Any]) -> int:
        """存储传感器数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 提取数据字段
            services = data.get("services", {})
            if isinstance(services, list) and len(services) > 0:
                service_data = services[0]
                properties = service_data.get("properties", {}) if isinstance(service_data, dict) else {}
            else:
                properties = services.get("properties", {}) if isinstance(services, dict) else {}

            cursor.execute('''
                INSERT INTO sensor_data (
                    device_id, crop_area_id, temperature, humidity, noise,
                    pm25, pm10, atmospheric_pressure, light_lux,
                    soil_temperature, soil_humidity, soil_conductivity, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                properties.get("cropArea_id", 1),
                properties.get("temperature"),
                properties.get("humidity"),
                properties.get("noise"),
                properties.get("PM25"),
                properties.get("PM10"),
                properties.get("atmospheric_pressure"),
                properties.get("light"),
                properties.get("soil_temperature"),
                properties.get("soil_humidity"),
                properties.get("soil_conductivity"),
                json.dumps(data)
            ))

            data_id = cursor.lastrowid

            # 更新设备的最后在线时间
            cursor.execute('''
                UPDATE devices 
                SET last_seen = ? 
                WHERE device_id = ?
            ''', (datetime.now().isoformat(), device_id))

            conn.commit()
            logger.debug(f"传感器数据存储成功: device_id={device_id}, data_id={data_id}")
            return data_id

        except sqlite3.Error as e:
            logger.error(f"存储传感器数据失败: {e}")
            if conn:
                conn.rollback()
            raise
        except Exception as e:
            logger.error(f"存储传感器数据时发生未知错误: {e}")
            raise

    def get_latest_sensor_data(self, device_id: str, limit: int = 10) -> List[Dict]:
        """获取设备的最新传感器数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sensor_data 
                WHERE device_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (device_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取传感器数据失败: {e}")
            return []

    def get_device_statistics(self, device_id: str) -> Dict:
        """获取设备统计信息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_records,
                    MIN(timestamp) as first_record,
                    MAX(timestamp) as last_record,
                    AVG(temperature) as avg_temperature,
                    AVG(humidity) as avg_humidity,
                    AVG(noise) as avg_noise,
                    AVG(pm25) as avg_pm25,
                    AVG(pm10) as avg_pm10,
                    AVG(atmospheric_pressure) as avg_pressure,
                    AVG(light_lux) as avg_light
                FROM sensor_data 
                WHERE device_id = ?
            ''', (device_id,))

            row = cursor.fetchone()
            if row:
                result = dict(row)
            else:
                result = {}
            return result

        except sqlite3.Error as e:
            logger.error(f"获取设备统计信息失败: {e}")
            return {}

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            logger.info("数据库连接已关闭")