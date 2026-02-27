import logging

import requests

import config

logger = logging.getLogger(__name__)


def send_telegram(message):
    """텔레그램 봇으로 메시지 전송."""
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("텔레그램 미설정 — 알림 스킵")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": f"[SmartFarm] {message}",
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.ok:
            logger.info("텔레그램 전송 성공")
            return True
        logger.warning("텔레그램 전송 실패: %s", resp.text)
        return False
    except Exception as e:
        logger.error("텔레그램 오류: %s", e)
        return False
