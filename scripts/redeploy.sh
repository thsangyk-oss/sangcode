#!/bin/bash
cd /root/sangcode
kill $(lsof -ti :8770) 2>/dev/null
# Kill ttyd pool
for p in $(seq 7681 7781); do kill $(lsof -ti :$p) 2>/dev/null; done
sleep 1
SANGCODE_BASE_PATH="" SANGCODE_PASSWORD="thanhsang123456" nohup python3 app.py > logs/sangcode.log 2>&1 &
sleep 1
curl -s http://localhost:8770/health && echo " OK"
