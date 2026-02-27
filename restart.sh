#!/bin/bash
# SmartFarm Flask 앱 재시작 스크립트

cd /home/berry/workspace/smartfarm

# 기존 프로세스 종료
kill $(lsof -t -i:5000) 2>/dev/null
sleep 1

# venv 활성화 후 실행
source venv/bin/activate
python app.py &

echo "SmartFarm 재시작 완료 (port 5000)"
