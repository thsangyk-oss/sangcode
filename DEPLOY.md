# DEPLOY.md — mycode / code.misanet.io.vn

## App
- **Repo:** `/root/mycode`
- **Domain:** `https://code.misanet.io.vn`
- **Local port:** `8770`
- **Service:** `mycode.service`
- **Runtime:** `python3 app.py`
- **Reverse proxy:** Caddy route `code.misanet.io.vn -> 172.17.0.1:8770`

## Important runtime settings
- Password env: `SANGCODE_PASSWORD`
- Data dir: `/root/mycode/data`
- Log file: `/root/mycode/logs/mycode.log`
- Session prefix (new): `mycode`
- Legacy session prefix still supported: `sangcode`

## Quick redeploy
```bash
cd /root/mycode
bash scripts/redeploy.sh
```

## First-time systemd install
```bash
cd /root/mycode
cp systemd/mycode.service /etc/systemd/system/mycode.service
systemctl daemon-reload
systemctl enable mycode.service
systemctl restart mycode.service
systemctl status mycode.service --no-pager
```

## Manual restart
```bash
systemctl restart mycode.service
systemctl status mycode.service --no-pager
```

## Logs
```bash
tail -100 /root/mycode/logs/mycode.log
journalctl -u mycode.service -n 100 --no-pager
journalctl -u mycode.service -f
```

## Health check
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8770/health
curl -s -o /dev/null -w "%{http_code}\n" https://code.misanet.io.vn/health
curl -s -o /dev/null -w "%{http_code}\n" https://code.misanet.io.vn/
```

Expected:
- `/health` => `200`
- `/` => `401` before login

## Notes
- App now auto-recovers tmux sessions with prefixes `mycode-*` and legacy `sangcode-*` on startup.
- If dashboard is empty but `tmux ls` still shows sessions, run:
```bash
systemctl restart mycode.service
```
- If domain returns `502`, check:
```bash
ss -tlnp | grep ':8770'
systemctl status mycode.service --no-pager
tail -100 /root/mycode/logs/mycode.log
```

## Git snapshot after fixes
After code changes, commit from repo root:
```bash
cd /root/mycode
git add app.py config.py tmux_manager.py ttyd_manager.py scripts/redeploy.sh systemd/mycode.service DEPLOY.md
# plus any other intended files
git commit -m "fix: stabilize mycode service and deploy flow"
```
