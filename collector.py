import json
import logging
import random
import threading
import time

import config
import database

logger = logging.getLogger(__name__)


class RS485Collector:
    def __init__(self):
        self._latest_data = {}
        self._lock = threading.Lock()
        self._serial = None
        self._use_mock = True
        self._running = False
        self._thread = None
        self._try_serial()

    def _try_serial(self):
        try:
            import serial
            self._serial = serial.Serial(
                config.RS485_PORT,
                config.RS485_BAUDRATE,
                timeout=config.RS485_TIMEOUT,
            )
            self._use_mock = False
            logger.info("RS485 연결 성공: %s", config.RS485_PORT)
        except Exception:
            self._use_mock = True
            logger.warning("RS485 연결 실패 — Mock 모드로 전환")

    @property
    def use_mock(self):
        return self._use_mock

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("수집기 시작 (mock=%s)", self._use_mock)

    def stop(self):
        self._running = False
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass

    def get_latest(self, device_id=None):
        with self._lock:
            if device_id:
                return self._latest_data.get(device_id)
            return dict(self._latest_data)

    def send_command(self, device_id, fan, heater, humid):
        """제어 명령 전송. 성공 시 True."""
        if self._use_mock:
            logger.info("[Mock] CMD:%s:%d,%d,%d", device_id, fan, heater, humid)
            with self._lock:
                if device_id in self._latest_data:
                    self._latest_data[device_id]["fan"] = fan
                    self._latest_data[device_id]["heater"] = heater
                    self._latest_data[device_id]["humid"] = humid
            return True

        cmd = f"CMD:{device_id}:{fan},{heater},{humid}\n"
        try:
            self._serial.write(cmd.encode())
            line = self._serial.readline().decode().strip()
            if line == f"ACK:{device_id}":
                logger.info("명령 성공: %s", cmd.strip())
                return True
            logger.warning("ACK 불일치: expected ACK:%s, got %s", device_id, line)
            return False
        except Exception as e:
            logger.error("명령 전송 실패: %s", e)
            return False

    # --- private ---

    def _poll_loop(self):
        while self._running:
            try:
                self._poll_all_nodes()
            except Exception as e:
                logger.error("폴링 오류: %s", e)
            time.sleep(config.COLLECT_INTERVAL_SECONDS)

    def _poll_all_nodes(self):
        for node in config.FARM_NODES:
            if not self._running:
                break
            data = self._poll_node(node["id"])
            if data:
                with self._lock:
                    self._latest_data[node["id"]] = data
                try:
                    database.insert_sensor_data(
                        data["id"], data["temp"], data["humi"],
                        data["fan"], data["heater"], data["humid"],
                    )
                except Exception as e:
                    logger.error("DB 저장 실패: %s", e)
            time.sleep(config.RS485_NODE_DELAY)

    def _poll_node(self, device_id):
        if self._use_mock:
            return self._mock_data(device_id)
        return self._serial_poll(device_id)

    def _serial_poll(self, device_id):
        try:
            self._serial.reset_input_buffer()
            self._serial.write(f"REQ:{device_id}\n".encode())
            line = self._serial.readline().decode().strip()
            if not line:
                logger.warning("노드 %s 응답 없음", device_id)
                return None
            data = json.loads(line)
            return data
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("노드 %s 파싱 오류: %s", device_id, e)
            return None
        except Exception as e:
            logger.error("노드 %s 통신 오류: %s", device_id, e)
            self._handle_serial_error()
            return None

    def _handle_serial_error(self):
        """시리얼 포트 재연결 시도."""
        logger.info("시리얼 포트 재연결 시도...")
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        time.sleep(2)
        self._try_serial()

    def _mock_data(self, device_id):
        with self._lock:
            prev = self._latest_data.get(device_id)
        if prev:
            temp = prev["temp"] + random.uniform(-0.5, 0.5)
            humi = prev["humi"] + random.uniform(-1.0, 1.0)
            fan = prev.get("fan", 0)
            heater = prev.get("heater", 0)
            humid = prev.get("humid", 0)
        else:
            temp = random.uniform(18, 32)
            humi = random.uniform(40, 80)
            fan = 0
            heater = 0
            humid = 0
        return {
            "id": device_id,
            "temp": round(max(5, min(45, temp)), 1),
            "humi": round(max(20, min(99, humi)), 1),
            "fan": fan,
            "heater": heater,
            "humid": humid,
        }
