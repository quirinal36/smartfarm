import threading
import time
import random
from flask import Flask, render_template, jsonify
import serial

app = Flask(__name__)

# 최신 센서 데이터 저장
sensor_data = {"temperature": None, "humidity": None}
lock = threading.Lock()

# 시리얼 포트 설정 (Arduino 연결 시 변경)
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUD = 9600
USE_MOCK = True  # 시리얼 장치 없으면 자동으로 True


def read_serial():
    """Arduino에서 시리얼 데이터를 읽는 스레드."""
    global USE_MOCK
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
        USE_MOCK = False
        print(f"[Serial] {SERIAL_PORT} 연결됨")
        time.sleep(2)  # Arduino 리셋 대기

        while True:
            line = ser.readline().decode("utf-8").strip()
            if line:
                try:
                    temp, hum = line.split(",")
                    with lock:
                        sensor_data["temperature"] = round(float(temp), 1)
                        sensor_data["humidity"] = round(float(hum), 1)
                except ValueError:
                    pass
    except serial.SerialException:
        USE_MOCK = True
        print(f"[Serial] {SERIAL_PORT} 연결 실패 - Mock 모드로 전환")


def read_mock():
    """테스트용 랜덤 데이터 생성."""
    while True:
        with lock:
            sensor_data["temperature"] = round(random.uniform(18, 32), 1)
            sensor_data["humidity"] = round(random.uniform(40, 80), 1)
        time.sleep(3)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/sensor")
def api_sensor():
    with lock:
        return jsonify({
            "temperature": sensor_data["temperature"],
            "humidity": sensor_data["humidity"],
            "mock": USE_MOCK,
        })


if __name__ == "__main__":
    # 시리얼 읽기 시도 → 실패 시 Mock 스레드 시작
    serial_thread = threading.Thread(target=read_serial, daemon=True)
    serial_thread.start()
    time.sleep(1)  # 연결 시도 대기

    if USE_MOCK:
        mock_thread = threading.Thread(target=read_mock, daemon=True)
        mock_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=False)
