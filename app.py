import logging
import os
import signal
import subprocess
import sys
from functools import wraps
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import ai_controller
import config
import database
from collector import RS485Collector
from notifier import send_telegram

# --- Logging ---
os.makedirs(config.LOG_DIR, exist_ok=True)

file_handler = RotatingFileHandler(
    os.path.join(config.LOG_DIR, "smartfarm.log"),
    maxBytes=config.LOG_MAX_BYTES,
    backupCount=config.LOG_BACKUP_COUNT,
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(), file_handler],
)
logger = logging.getLogger(__name__)

# --- Flask ---
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# --- Global objects ---
collector_instance = None
scheduler = None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# === Page routes ===

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        error = "아이디 또는 비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


# === REST API ===

@app.route("/api/latest")
@login_required
def api_latest():
    latest_cache = collector_instance.get_latest() if collector_instance else {}
    from datetime import datetime, timedelta

    data = []
    for node in config.FARM_NODES:
        nid = node["id"]
        cached = latest_cache.get(nid)
        if cached:
            data.append({
                "id": nid,
                "name": node["name"],
                "crop": node["crop"],
                "temp": cached["temp"],
                "humi": cached["humi"],
                "fan": cached["fan"],
                "heater": cached["heater"],
                "humid": cached["humid"],
                "online": True,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            })
        else:
            data.append({
                "id": nid,
                "name": node["name"],
                "crop": node["crop"],
                "temp": None, "humi": None,
                "fan": 0, "heater": 0, "humid": 0,
                "online": False,
                "timestamp": None,
            })

    return jsonify({
        "data": data,
        "mock": collector_instance.use_mock if collector_instance else True,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    })


@app.route("/api/history/<device_id>")
@login_required
def api_history(device_id):
    hours = request.args.get("hours", 12, type=int)
    rows = database.get_history(device_id, hours)
    return jsonify({"device_id": device_id, "data": rows})


@app.route("/api/ai-logs")
@login_required
def api_ai_logs():
    limit = request.args.get("limit", 20, type=int)
    logs = database.get_ai_logs(limit)
    return jsonify({"logs": logs})


@app.route("/api/system")
@login_required
def api_system():
    cpu_temp = _get_cpu_temp()
    uptime = _get_uptime()
    online = 0
    if collector_instance:
        latest = collector_instance.get_latest()
        online = len(latest)
    return jsonify({
        "cpu_temp": cpu_temp,
        "uptime": uptime,
        "node_count": len(config.FARM_NODES),
        "online_count": online,
        "mock": collector_instance.use_mock if collector_instance else True,
        "timestamp": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    })


@app.route("/api/command", methods=["POST"])
@login_required
def api_command():
    data = request.get_json()
    if not data or "device_id" not in data:
        return jsonify({"success": False, "error": "device_id 필요"}), 400

    device_id = data["device_id"]
    fan = int(data.get("fan", False))
    heater = int(data.get("heater", False))
    humidifier = int(data.get("humidifier", False))

    ok = collector_instance.send_command(device_id, fan, heater, humidifier) if collector_instance else False
    if ok:
        database.insert_ai_log(
            device_id,
            "수동 제어",
            f"fan={fan}, heater={heater}, humid={humidifier}",
            fan, heater, humidifier,
        )
    return jsonify({"success": ok, "device_id": device_id})


# === Helpers ===

def _get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


def _get_uptime():
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return "unknown"


# === Startup / Shutdown ===

def start_services():
    global collector_instance, scheduler

    database.init_db()
    logger.info("DB 초기화 완료")

    collector_instance = RS485Collector()
    collector_instance.start()
    logger.info("수집기 시작")

    ai_controller.set_notifier(send_telegram)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: ai_controller.run_ai_cycle(collector_instance),
        "interval", minutes=config.AI_INTERVAL_MINUTES,
        id="ai_cycle", replace_existing=True,
    )
    scheduler.add_job(
        database.cleanup_old_data,
        "cron", hour=3, minute=0,
        id="cleanup", replace_existing=True,
    )
    scheduler.start()
    logger.info("스케줄러 시작 (AI %d분, 정리 03:00)", config.AI_INTERVAL_MINUTES)


def shutdown(signum=None, frame=None):
    logger.info("종료 시작...")
    if scheduler:
        scheduler.shutdown(wait=False)
    if collector_instance:
        collector_instance.stop()
    logger.info("종료 완료")
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


if __name__ == "__main__":
    start_services()
    logger.info("Flask 서버 시작 — %s:%s", config.DASHBOARD_HOST, config.DASHBOARD_PORT)
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=False,
    )
