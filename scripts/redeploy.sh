#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/mycode"
LOG_FILE="$APP_DIR/logs/mycode.log"
SERVICE_NAME="mycode.service"
PASSWORD="${SANGCODE_PASSWORD:-thanhsang123456}"

cd "$APP_DIR"
mkdir -p logs data

echo '[redeploy] syntax check'
python3 -m py_compile app.py config.py tmux_manager.py ttyd_manager.py registry.py monitor.py

echo '[redeploy] reload systemd'
systemctl daemon-reload

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}"; then
  echo '[redeploy] restart systemd service'
  systemctl restart "$SERVICE_NAME"
else
  echo '[redeploy] service not installed yet; starting manual process'
  if lsof -t -i:8770 >/dev/null 2>&1; then
    lsof -t -i:8770 | xargs -r kill || true
    sleep 1
  fi
  export SANGCODE_HOST='0.0.0.0'
  export SANGCODE_PORT='8770'
  export SANGCODE_BASE_PATH=''
  export SANGCODE_PASSWORD="$PASSWORD"
  export SANGCODE_WORKSPACE='/root'
  export SANGCODE_DATA='/root/mycode/data'
  export SANGCODE_SESSION_PREFIX='mycode'
  export SANGCODE_LEGACY_SESSION_PREFIXES='sangcode'
  nohup python3 app.py >> "$LOG_FILE" 2>&1 &
  sleep 3
fi

echo '[redeploy] health checks'
printf 'localhost /health => '
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8770/health
printf 'domain /health => '
curl -k -s -o /dev/null -w '%{http_code}\n' https://code.misanet.io.vn/health
printf 'domain / => '
curl -k -s -o /dev/null -w '%{http_code}\n' https://code.misanet.io.vn/
printf 'domain / with cookie => '
curl -k -s -o /dev/null -w '%{http_code}\n' --cookie "sangcode_auth=$PASSWORD" https://code.misanet.io.vn/
printf 'api/sessions => '
curl -k -s -o /dev/null -w '%{http_code}\n' --cookie "sangcode_auth=$PASSWORD" https://code.misanet.io.vn/api/sessions

echo '[redeploy] done'
