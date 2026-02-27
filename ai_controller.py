import json
import logging
from datetime import datetime

import config
import database

logger = logging.getLogger(__name__)

_notifier = None


def set_notifier(notifier_func):
    global _notifier
    _notifier = notifier_func


def run_ai_cycle(collector):
    """AI 제어 사이클 1회 실행."""
    latest = collector.get_latest()
    if not latest:
        logger.warning("센서 데이터 없음 — AI 사이클 스킵")
        return

    decisions = _get_ai_decisions(latest)
    if not decisions:
        return

    for d in decisions.get("decisions", []):
        device_id = d["id"]
        fan = int(d.get("fan", False))
        heater = int(d.get("heater", False))
        humid = int(d.get("humidifier", False))

        collector.send_command(device_id, fan, heater, humid)

        parts = []
        if fan:
            parts.append("환풍기 ON")
        if heater:
            parts.append("히터 ON")
        if humid:
            parts.append("가습기 ON")
        action = ", ".join(parts) if parts else "유지"

        alert = decisions.get("alert")
        database.insert_ai_log(
            device_id, action, d.get("reason", ""),
            fan, heater, humid, alert,
        )

    if decisions.get("alert") and _notifier:
        try:
            _notifier(decisions["alert"])
        except Exception as e:
            logger.error("알림 전송 실패: %s", e)


def _get_ai_decisions(latest_data):
    """OpenAI 호출 시도, 실패 시 폴백 규칙 적용."""
    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "sk-your-key-here":
        logger.info("API 키 미설정 — 폴백 규칙 적용")
        return _fallback_decisions(latest_data)

    try:
        return _call_openai(latest_data)
    except Exception as e:
        logger.error("OpenAI API 호출 실패: %s — 폴백 규칙 적용", e)
        return _fallback_decisions(latest_data)


def _call_openai(latest_data):
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    prompt = _build_prompt(latest_data)
    logger.debug("AI 프롬프트:\n%s", prompt)

    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=config.OPENAI_TEMPERATURE,
        max_tokens=config.OPENAI_MAX_TOKENS,
        messages=[
            {"role": "system", "content": (
                "너는 스마트팜 환경 제어 AI다. "
                "주어진 센서 데이터를 분석하고, 각 구역의 환풍기/히터/가습기를 제어하라. "
                "반드시 지정된 JSON 형식으로만 응답하라."
            )},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    text = resp.choices[0].message.content
    result = json.loads(text)
    logger.info("AI 응답: %s", json.dumps(result, ensure_ascii=False)[:200])
    return result


def _build_prompt(latest_data):
    now = datetime.now()
    hour = now.hour
    month = now.month
    if month in (3, 4, 5):
        season = "봄"
    elif month in (6, 7, 8):
        season = "여름"
    elif month in (9, 10, 11):
        season = "가을"
    else:
        season = "겨울"
    time_period = "주간" if 6 <= hour < 18 else "야간"

    zones = []
    for node in config.FARM_NODES:
        nid = node["id"]
        data = latest_data.get(nid)
        crop = node["crop"]
        crop_range = config.CROP_RANGES.get(crop, {})
        if data:
            zones.append(
                f"- {nid} ({node['name']}): "
                f"온도 {data['temp']}°C, 습도 {data['humi']}%, "
                f"환풍기 {'ON' if data['fan'] else 'OFF'}, "
                f"히터 {'ON' if data['heater'] else 'OFF'}, "
                f"가습기 {'ON' if data['humid'] else 'OFF'}\n"
                f"  적정범위: 온도 {crop_range.get('temp_min', '?')}~{crop_range.get('temp_max', '?')}°C, "
                f"습도 {crop_range.get('humi_min', '?')}~{crop_range.get('humi_max', '?')}%"
            )

    return f"""현재 시각: {now.strftime('%Y-%m-%d %H:%M')} ({time_period})
계절: {season}

=== 구역별 센서 데이터 ===
{chr(10).join(zones)}

위 데이터를 분석하여 각 구역의 환풍기/히터/가습기 ON/OFF를 결정하라.
아래 JSON 형식으로 응답:
{{
  "decisions": [
    {{"id": "FARM_XX", "fan": true/false, "heater": true/false, "humidifier": true/false, "reason": "판단 이유(한국어)"}}
  ],
  "summary": "전체 상황 요약(한국어)",
  "alert": "긴급 알림 메시지 또는 null"
}}"""


def _fallback_decisions(latest_data):
    """API 실패 시 단순 규칙 기반 판단."""
    rules = config.SAFETY_RULES
    decisions = []
    alert = None

    for node in config.FARM_NODES:
        nid = node["id"]
        data = latest_data.get(nid)
        if not data:
            continue

        fan = False
        heater = False
        humid = False
        reasons = []

        if data["temp"] > rules["temp_max"]:
            fan = True
            reasons.append(f"온도 {data['temp']}°C > {rules['temp_max']}°C")
        if data["temp"] < rules["temp_min"]:
            heater = True
            reasons.append(f"온도 {data['temp']}°C < {rules['temp_min']}°C")
        if data["humi"] > rules["humi_max"]:
            fan = True
            reasons.append(f"습도 {data['humi']}% > {rules['humi_max']}%")
        if data["humi"] < rules["humi_min"]:
            humid = True
            reasons.append(f"습도 {data['humi']}% < {rules['humi_min']}%")

        if data["temp"] > 40 or data["temp"] < 3:
            alert = f"[긴급] {nid} 온도 {data['temp']}°C — 비상 상태"

        reason = "[폴백] " + (", ".join(reasons) if reasons else "정상 범위")
        decisions.append({
            "id": nid,
            "fan": fan,
            "heater": heater,
            "humidifier": humid,
            "reason": reason,
        })

    return {
        "decisions": decisions,
        "summary": "[폴백 규칙 적용] API 키 미설정 또는 호출 실패",
        "alert": alert,
    }
