# 🌱 스마트팜 모니터링 & AI 제어 시스템

## Product Requirements Document (PRD)

---

## 1. 프로젝트 개요

### 1-1. 목적

비닐하우스 내부의 온·습도를 실시간 모니터링하고, OpenAI API 기반 AI가 환풍기/히터/가습기를 자동 제어하는 스마트팜 시스템의 **서버 애플리케이션**을 구축한다.

### 1-2. 실행 환경

| 항목 | 사양 |
|------|------|
| 하드웨어 | Raspberry Pi 4 (2GB 이상) |
| OS | Raspberry Pi OS (64-bit) |
| Python | 3.11+ |
| 네트워크 | LTE 테더링 (WiFi) |
| 외부 접속 | Cloudflare Tunnel → 커스텀 도메인 |

### 1-3. 연결 장치

| 장치 | 역할 | 통신 |
|------|------|------|
| Arduino Pro Mini 5V × N대 | 센서 노드 (온습도 측정, 릴레이 제어) | RS485 (9600bps) |
| MFA-02 USB-to-RS485 | RPi ↔ RS485 버스 변환 | USB Serial |
| SMG-A RS485 모듈 | Arduino ↔ RS485 변환 (자동 흐름제어) | TTL ↔ RS485 |
| DHT22 (AM2302) | 온도 ±0.5°C / 습도 ±2% 센서 | 1-Wire |

---

## 2. 시스템 아키텍처

### 2-1. 전체 구조

```
[Arduino 노드 #1~N]
  └ DHT22 센서
  └ 릴레이 (환풍기/히터/가습기)
  └ SMG-A RS485 모듈
        │
        │ RS485 (UL2919 AWG20 케이블)
        │
[Raspberry Pi 4]
  ├ MFA-02 USB-to-RS485
  ├ collector.py ──── RS485 폴링으로 센서 데이터 수집
  ├ database.py ───── SQLite DB 저장/조회
  ├ ai_controller.py ── OpenAI API로 제어 판단
  ├ app.py ─────────── Flask 웹 서버 (대시보드 + API)
  ├ notifier.py ────── 텔레그램 알림 (선택)
  └ config.py ─────── 환경 설정
        │
        │ Cloudflare Tunnel (HTTPS)
        │
[외부 브라우저] ── https://farm.yourdomain.com
```

### 2-2. 디렉토리 구조

```
/home/pi/smartfarm/
├── .env                      # API 키, 시크릿 (git 미포함)
├── config.py                 # 설정값
├── database.py               # DB 초기화 및 유틸
├── collector.py              # RS485 데이터 수집 서비스
├── ai_controller.py          # OpenAI API 제어 엔진
├── notifier.py               # 텔레그램 알림
├── app.py                    # Flask 메인 서버 (진입점)
├── requirements.txt          # Python 패키지
├── templates/
│   ├── login.html            # 로그인 페이지
│   └── dashboard.html        # 대시보드 메인
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── dashboard.js      # 대시보드 프론트엔드 로직
├── smartfarm.db              # SQLite 데이터베이스 (자동 생성)
└── logs/
    └── smartfarm.log         # 애플리케이션 로그
```

---

## 3. RS485 통신 프로토콜

### 3-1. Master-Slave 폴링 방식

RPi(Master)가 각 Arduino 노드(Slave)에 순서대로 요청하고, 해당 노드만 응답한다.

### 3-2. 메시지 규격

**데이터 요청 (RPi → Arduino)**

```
REQ:{DEVICE_ID}\n
```

예: `REQ:FARM_01\n`

**데이터 응답 (Arduino → RPi)**

```json
{"id":"FARM_01","temp":25.3,"humi":68.0,"fan":0,"heater":1,"humid":0}\n
```

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string | 노드 식별자 |
| temp | float | 온도 (°C, 소수점 1자리) |
| humi | float | 습도 (%, 소수점 1자리) |
| fan | int | 환풍기 상태 (0=OFF, 1=ON) |
| heater | int | 히터 상태 (0=OFF, 1=ON) |
| humid | int | 가습기 상태 (0=OFF, 1=ON) |

**제어 명령 (RPi → Arduino)**

```
CMD:{DEVICE_ID}:{fan},{heater},{humidifier}\n
```

예: `CMD:FARM_01:1,0,0\n` (환풍기 ON, 히터 OFF, 가습기 OFF)

**제어 확인 (Arduino → RPi)**

```
ACK:{DEVICE_ID}\n
```

### 3-3. 통신 파라미터

| 항목 | 값 |
|------|-----|
| Baud Rate | 9600 |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |
| 응답 타임아웃 | 2초 |
| 노드 간 요청 간격 | 300ms |
| 전체 수집 주기 | 30초 |

---

## 4. 데이터베이스 설계

### 4-1. DBMS

SQLite 3 (파일: `smartfarm.db`)

### 4-2. 테이블

**sensor_data** — 센서 데이터 이력

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 레코드 ID |
| device_id | TEXT NOT NULL | 노드 식별자 |
| temp | REAL | 온도 (°C) |
| humi | REAL | 습도 (%) |
| fan | INTEGER DEFAULT 0 | 환풍기 상태 |
| heater | INTEGER DEFAULT 0 | 히터 상태 |
| humid | INTEGER DEFAULT 0 | 가습기 상태 |
| timestamp | DATETIME DEFAULT CURRENT_TIMESTAMP | 기록 시각 |

인덱스: `(device_id, timestamp DESC)`

**ai_logs** — AI 판단 로그

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 레코드 ID |
| device_id | TEXT NOT NULL | 대상 노드 |
| action | TEXT | 수행 동작 (예: "환풍기 ON") |
| reason | TEXT | AI 판단 이유 |
| fan_cmd | INTEGER | 환풍기 명령 (0/1) |
| heater_cmd | INTEGER | 히터 명령 (0/1) |
| humid_cmd | INTEGER | 가습기 명령 (0/1) |
| alert | TEXT | 긴급 알림 메시지 (nullable) |
| timestamp | DATETIME DEFAULT CURRENT_TIMESTAMP | 판단 시각 |

### 4-3. 데이터 관리

- 30일 이전 데이터 자동 삭제 (매일 새벽 3시)
- SD 카드 수명 보호 목적

---

## 5. API 엔드포인트

### 5-1. 페이지 라우트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET/POST | `/login` | 로그인 페이지 | 불필요 |
| GET | `/logout` | 로그아웃 | 불필요 |
| GET | `/` | 대시보드 메인 | 필요 |

### 5-2. REST API

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET | `/api/latest` | 각 노드의 최신 센서 데이터 | 필요 |
| GET | `/api/history/<device_id>` | 특정 노드의 시간별 이력 | 필요 |
| GET | `/api/ai-logs` | 최근 AI 판단 로그 | 필요 |
| GET | `/api/system` | RPi 시스템 상태 | 필요 |
| POST | `/api/command` | 수동 제어 명령 전송 | 필요 |

### 5-3. API 응답 형식

모든 API는 JSON으로 응답한다.

**GET /api/latest**

```json
{
  "data": [
    {
      "id": "FARM_01",
      "name": "1구역 · 토마토",
      "crop": "토마토",
      "temp": 25.3,
      "humi": 68.0,
      "fan": 0,
      "heater": 1,
      "humid": 0,
      "online": true,
      "timestamp": "2026-02-19T14:30:05"
    }
  ],
  "timestamp": "2026-02-19T14:30:10"
}
```

**GET /api/history/FARM_01?hours=12**

```json
{
  "device_id": "FARM_01",
  "data": [
    {"temp": 22.1, "humi": 70.0, "fan": 0, "heater": 0, "humid": 0, "timestamp": "2026-02-19T08:00:00"},
    {"temp": 23.0, "humi": 69.5, "fan": 0, "heater": 0, "humid": 0, "timestamp": "2026-02-19T08:30:00"}
  ]
}
```

**GET /api/ai-logs?limit=20**

```json
{
  "logs": [
    {
      "device_id": "FARM_01",
      "action": "환풍기 ON",
      "reason": "온도 32.1°C로 적정 범위 초과",
      "fan_cmd": 1,
      "heater_cmd": 0,
      "humid_cmd": 0,
      "alert": null,
      "timestamp": "2026-02-19T14:30:00"
    }
  ]
}
```

**GET /api/system**

```json
{
  "cpu_temp": 48.2,
  "uptime": "up 3 days, 14 hours",
  "node_count": 3,
  "online_count": 3,
  "timestamp": "2026-02-19T14:30:10"
}
```

**POST /api/command**

요청:

```json
{
  "device_id": "FARM_01",
  "fan": true,
  "heater": false,
  "humidifier": false
}
```

응답:

```json
{
  "success": true,
  "device_id": "FARM_01"
}
```

---

## 6. OpenAI API 연동

### 6-1. 사용 모델

| 항목 | 값 |
|------|-----|
| 모델 | gpt-4o-mini |
| temperature | 0.1 (일관된 판단) |
| max_tokens | 800 |
| 호출 주기 | 5분 |
| 예상 월 비용 | ~2,000원 |

### 6-2. 프롬프트 구성

AI에게 전달하는 정보:

- 현재 시각 (주간/야간 구분)
- 계절 정보
- 각 구역별 센서 데이터 (온도, 습도)
- 각 구역의 작물 종류
- 작물별 적정 온습도 범위

### 6-3. AI 응답 형식 (JSON)

```json
{
  "decisions": [
    {
      "id": "FARM_01",
      "fan": true,
      "heater": false,
      "humidifier": false,
      "reason": "판단 이유 (한국어)"
    }
  ],
  "summary": "전체 상황 요약 (한국어)",
  "alert": "긴급 알림 (없으면 null)"
}
```

### 6-4. 폴백 규칙

API 호출 실패 시 RPi 측에서 적용하는 기본 규칙:

| 조건 | 동작 |
|------|------|
| 온도 > 35°C | 환풍기 ON |
| 온도 < 10°C | 히터 ON |
| 습도 > 90% | 환풍기 ON |
| 습도 < 40% | 가습기 ON |

Arduino 측 비상 안전 규칙 (항상 동작, AI 무관):

| 조건 | 동작 |
|------|------|
| 온도 > 40°C | 히터 강제 OFF |
| 온도 < 3°C | 히터 강제 ON |
| 습도 > 95% | 환풍기 강제 ON |

---

## 7. 대시보드 UI

### 7-1. 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Flask (Python) |
| 프론트엔드 | HTML + Vanilla JS + CSS |
| 차트 | Chart.js (CDN) |
| 폰트 | Noto Sans KR + JetBrains Mono (Google Fonts CDN) |
| 스타일 | 다크 테마 |

### 7-2. 화면 구성

**로그인 페이지 (`/login`)**

- 아이디, 비밀번호 입력
- Flask session 기반 인증

**대시보드 메인 (`/`)**

```
┌─ 헤더 ──────────────────────────────────────────────┐
│ 🌱 Smart Farm  [AI ACTIVE]           2026-02-19     │
│                                      14:30:05       │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─ 구역 카드 ────┐ ┌─ 상세 차트 ────┐ ┌─ AI 로그 ─┐ │
│ │ FARM_01        │ │ 선택된 구역의  │ │ 시간 구역  │ │
│ │ 온도 26.3°C    │ │ 12시간 추이    │ │ 동작 이유  │ │
│ │ 습도 68.5%     │ │                │ │           │ │
│ │ 🟢환풍기 히터  │ │ 온도 그래프    │ │ 14:30     │ │
│ │ [수동제어 버튼]│ │ 습도 그래프    │ │ FARM_02   │ │
│ ├────────────────┤ │                │ │ 환풍기 ON │ │
│ │ FARM_02        │ ├────────────────┤ │           │ │
│ │ 온도 32.1°C ⚠️│ │ 시스템 상태    │ ├───────────┤ │
│ │ 습도 85.2%     │ │ CPU 48.2°C    │ │ AI 요약   │ │
│ │ ...            │ │ 가동 3일 14시간│ │           │ │
│ ├────────────────┤ │ 온라인 3/3    │ │ 2구역 고온│ │
│ │ FARM_03        │ │ ...           │ │ 주의 ...  │ │
│ │ ...            │ │               │ │           │ │
│ └────────────────┘ └───────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────┘
```

### 7-3. 자동 갱신 주기

| 대상 | 주기 |
|------|------|
| 센서 데이터 (api/latest) | 10초 |
| AI 로그 (api/ai-logs) | 60초 |
| 시스템 상태 (api/system) | 30초 |
| 시계 표시 | 1초 |

### 7-4. 상태 표시 기준

| 상태 | 조건 | 색상 |
|------|------|------|
| 정상 | 적정 범위 내 | 🟢 초록 |
| 주의 | 온도 ±5°C 이탈 또는 습도 80% 초과 | 🟡 노랑 |
| 경고 | 온도 ±10°C 이탈 또는 습도 90% 초과 | 🔴 빨강 |
| 오프라인 | 노드 응답 없음 | ⚫ 회색 |

---

## 8. 인증 및 보안

### 8-1. 로그인

| 항목 | 내용 |
|------|------|
| 방식 | Flask session 기반 |
| 계정 저장 | config.py 또는 .env |
| 초기 계정 | admin / 초기비밀번호 (변경 권장) |

### 8-2. 보안 고려사항

- Flask secret_key는 랜덤 생성하여 .env에 저장
- Cloudflare Access 연동 시 이메일 인증 추가 가능 (선택)
- API 엔드포인트 전체에 `@login_required` 적용
- .env 파일은 .gitignore에 포함

---

## 9. 스케줄링

| 작업 | 주기 | 라이브러리 |
|------|------|-----------|
| 센서 데이터 수집 (RS485 폴링) | 30초 | threading |
| AI 제어 판단 (OpenAI API) | 5분 | APScheduler |
| 오래된 데이터 삭제 | 매일 03:00 | APScheduler |

---

## 10. 설정 관리

### 10-1. config.py 주요 설정값

```python
# RS485
RS485_PORT = "/dev/ttyUSB0"
RS485_BAUDRATE = 9600
RS485_TIMEOUT = 2

# 센서 노드 목록
FARM_NODES = [
    {"id": "FARM_01", "name": "1구역 · 토마토", "crop": "토마토"},
    # 노드 추가 시 여기에 추가
]

# OpenAI
OPENAI_MODEL = "gpt-4o-mini"
AI_INTERVAL_MINUTES = 5

# 수집
COLLECT_INTERVAL_SECONDS = 30

# 대시보드
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# 안전 폴백 규칙
SAFETY_RULES = {
    "temp_max": 35.0,
    "temp_min": 10.0,
    "humi_max": 90.0,
    "humi_min": 40.0,
}
```

### 10-2. .env 파일

```
OPENAI_API_KEY=sk-xxxxx
FLASK_SECRET_KEY=랜덤문자열
TELEGRAM_BOT_TOKEN=xxxxx       # 선택
TELEGRAM_CHAT_ID=xxxxx         # 선택
```

---

## 11. 패키지 의존성

### requirements.txt

```
flask==3.1.0
pyserial==3.5
openai==1.82.0
apscheduler==3.11.0
requests==2.32.3
python-dotenv==1.1.0
```

---

## 12. 실행 방법

### 12-1. 개발/테스트

```bash
cd /home/pi/smartfarm
source venv/bin/activate
python app.py
```

### 12-2. 프로덕션 (systemd 서비스)

```ini
[Unit]
Description=Smart Farm Server
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/smartfarm
Environment=PATH=/home/pi/smartfarm/venv/bin:/usr/bin
ExecStart=/home/pi/smartfarm/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 13. 향후 확장 계획

| 단계 | 내용 | 우선순위 |
|------|------|:--------:|
| v1.0 | 센서 수집 + 대시보드 + AI 제어 (이 문서 범위) | 🔴 높음 |
| v1.1 | 텔레그램 알림 연동 | 🟡 중간 |
| v1.2 | 센서 데이터 CSV 내보내기 | 🟡 중간 |
| v2.0 | 다중 비닐하우스 지원 (하우스별 노드 그룹) | 🟢 낮음 |
| v2.1 | 사용자 관리 (다중 계정) | 🟢 낮음 |
| v2.2 | 모바일 반응형 UI 최적화 | 🟢 낮음 |