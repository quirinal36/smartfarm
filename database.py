import sqlite3
from datetime import datetime, timedelta
import config


def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            temp REAL,
            humi REAL,
            fan INTEGER DEFAULT 0,
            heater INTEGER DEFAULT 0,
            humid INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_sensor_device_time
            ON sensor_data (device_id, timestamp DESC);

        CREATE TABLE IF NOT EXISTS ai_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            action TEXT,
            reason TEXT,
            fan_cmd INTEGER,
            heater_cmd INTEGER,
            humid_cmd INTEGER,
            alert TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ailog_time
            ON ai_logs (timestamp DESC);
    """)
    conn.close()


def insert_sensor_data(device_id, temp, humi, fan, heater, humid):
    conn = _connect()
    conn.execute(
        "INSERT INTO sensor_data (device_id, temp, humi, fan, heater, humid) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (device_id, temp, humi, fan, heater, humid),
    )
    conn.commit()
    conn.close()


def get_latest_all():
    """각 device_id의 최신 레코드 1건씩 반환."""
    conn = _connect()
    rows = conn.execute("""
        SELECT s.* FROM sensor_data s
        INNER JOIN (
            SELECT device_id, MAX(timestamp) AS max_ts
            FROM sensor_data GROUP BY device_id
        ) g ON s.device_id = g.device_id AND s.timestamp = g.max_ts
        ORDER BY s.device_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history(device_id, hours=12):
    """특정 노드의 최근 N시간 이력."""
    conn = _connect()
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT temp, humi, fan, heater, humid, timestamp FROM sensor_data "
        "WHERE device_id = ? AND timestamp >= ? ORDER BY timestamp",
        (device_id, since),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_ai_log(device_id, action, reason, fan_cmd, heater_cmd, humid_cmd, alert=None):
    conn = _connect()
    conn.execute(
        "INSERT INTO ai_logs (device_id, action, reason, fan_cmd, heater_cmd, humid_cmd, alert) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (device_id, action, reason, fan_cmd, heater_cmd, humid_cmd, alert),
    )
    conn.commit()
    conn.close()


def get_ai_logs(limit=20):
    conn = _connect()
    rows = conn.execute(
        "SELECT device_id, action, reason, fan_cmd, heater_cmd, humid_cmd, alert, timestamp "
        "FROM ai_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cleanup_old_data():
    """보존 기간 이전 데이터 삭제."""
    cutoff = (datetime.utcnow() - timedelta(days=config.DATA_RETENTION_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = _connect()
    conn.execute("DELETE FROM sensor_data WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM ai_logs WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()
