import os
from dotenv import load_dotenv

load_dotenv()

# --- RS485 ---
RS485_PORT = os.getenv("RS485_PORT", "/dev/ttyUSB0")
RS485_BAUDRATE = 9600
RS485_TIMEOUT = 2
RS485_NODE_DELAY = 0.3  # 노드 간 요청 간격 (초)

# --- 센서 노드 목록 ---
FARM_NODES = [
    {"id": "FARM_01", "name": "1구역 · 토마토", "crop": "토마토"},
    {"id": "FARM_02", "name": "2구역 · 딸기", "crop": "딸기"},
    {"id": "FARM_03", "name": "3구역 · 상추", "crop": "상추"},
]

# --- 작물별 적정 범위 ---
CROP_RANGES = {
    "토마토": {"temp_min": 18, "temp_max": 30, "humi_min": 50, "humi_max": 80},
    "딸기":   {"temp_min": 15, "temp_max": 25, "humi_min": 60, "humi_max": 80},
    "상추":   {"temp_min": 15, "temp_max": 25, "humi_min": 50, "humi_max": 70},
}

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.1
OPENAI_MAX_TOKENS = 800
AI_INTERVAL_MINUTES = 5

# --- 수집 ---
COLLECT_INTERVAL_SECONDS = 30

# --- Flask ---
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# --- 인증 ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "leehg")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "gudrn!@09")

# --- 텔레그램 (선택) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- 데이터베이스 ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smartfarm.db")
DATA_RETENTION_DAYS = 30

# --- 안전 폴백 규칙 ---
SAFETY_RULES = {
    "temp_max": 35.0,
    "temp_min": 10.0,
    "humi_max": 90.0,
    "humi_min": 40.0,
}

# --- 로그 ---
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3
