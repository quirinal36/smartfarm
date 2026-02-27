# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SmartFarm is a Raspberry Pi-based IoT monitoring and AI control system for greenhouse agriculture. It collects sensor data from Arduino nodes via RS485, displays it on a web dashboard, and uses OpenAI GPT-4o-mini to make automated fan/heater/humidifier control decisions.

The primary documentation is in `PRD.md` (Korean). The system manages 3 farm zones (FARM_01~03) growing tomatoes, strawberries, and lettuce.

## Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app (listens on 0.0.0.0:5000)
python app.py
```

The app auto-falls back to mock mode when RS485 hardware (`/dev/ttyUSB0`) is unavailable, generating simulated sensor data for development.

**Systemd (production):**
```bash
sudo cp smartfarm.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now smartfarm
sudo journalctl -u smartfarm -f   # view logs
```

No test suite, linter, or CI/CD is configured.

## Architecture

```
Arduino Nodes ←RS485→ collector.py ←→ app.py (Flask) ←HTTP→ Browser Dashboard
                                        ↕              ↕
                               ai_controller.py    database.py
                                        ↓
                                   notifier.py (Telegram)
```

**Module responsibilities:**

| Module | Role |
|--------|------|
| `app.py` | Flask entry point. Routes, REST API, APScheduler setup, graceful shutdown |
| `collector.py` | Thread-safe RS485 serial polling (30s interval). Mock mode fallback. Caches latest readings |
| `ai_controller.py` | Calls OpenAI every 5 min to decide device actions. Falls back to hardcoded safety rules if API fails |
| `database.py` | SQLite with WAL mode. Two tables: `sensor_data`, `ai_logs`. Auto-cleanup at 30 days |
| `config.py` | Central config. Loads `.env` via python-dotenv. Farm nodes, crop ranges, safety thresholds |
| `notifier.py` | Optional Telegram alerts on AI emergency decisions |

**Frontend** (`templates/` + `static/`): Vanilla JS + CSS dark theme + Chart.js. No build step. Auto-refreshes sensor data (10s), AI logs (60s), system info (30s).

## Key Technical Details

- **RS485 protocol**: Request format `REQ:FARM_01\n`, response is JSON `{"id","temp","humi","fan","heater","humid"}`. Commands: `CMD:FARM_01:1,0,0\n` (fan,heater,humidifier as 0/1)
- **Database**: SQLite file `smartfarm.db`, auto-created on first run. Tables indexed on `(device_id, timestamp)`
- **Auth**: Flask session-based with `@login_required` decorator. Credentials from `.env` (`ADMIN_USERNAME`/`ADMIN_PASSWORD`)
- **AI fallback rules** (when OpenAI unavailable): temp>35°C→fan, temp<10°C→heater, humi>90%→fan, humi<40%→humidifier
- **Scheduling**: APScheduler runs collection (30s), AI cycle (5min), DB cleanup (daily 3AM)

## Environment Variables (.env)

Required: `OPENAI_API_KEY`, `FLASK_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`
Optional: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RS485_PORT`

## API Endpoints

- `GET /api/latest` — current sensor readings for all zones
- `GET /api/history/<device_id>?hours=12` — time-series data
- `GET /api/ai-logs?limit=20` — recent AI decisions
- `GET /api/system` — CPU temp, uptime, node count
- `POST /api/command` — manual device control `{device_id, fan, heater, humid}`

## Language

The codebase uses Korean for UI text, log messages, AI prompts, and crop names. Code identifiers and comments are in English.
