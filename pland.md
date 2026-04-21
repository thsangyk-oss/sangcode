# MyCode — Implementation Plan (ttyd-based, "xịn hơn vibecode")

> **Mục tiêu:** Build một web terminal dashboard xịn hơn vibecode, dùng **ttyd** để render terminal thật (xterm.js + WebSocket, không polling). Bám sát plan này, LLM cỡ trung có thể làm được end-to-end.
>
> **Đối tượng đọc:** LLM hoặc developer mid-level. Mỗi task đều có (a) lệnh cụ thể, (b) snippet code, (c) tiêu chí "done when…".

---

## 0. TL;DR — Kiến trúc 1 phút

```
Browser
  │
  │  HTTPS  →  Caddy  →  /mycode/*     (UI + API, port 8770)
  │                   →  /mycode/tty/* (ttyd WS, port 7681+)
  ▼
┌───────────────────────────────────────┐
│  Python backend (app.py, port 8770)   │
│   • Dashboard + API (Flask/stdlib)    │
│   • Session registry (JSON)           │
│   • Spawn ttyd processes              │
│   • Spawn/attach tmux sessions        │
│   • Auto-approve monitor loop         │
└───────────────────────────────────────┘
          │                  │
          ▼                  ▼
   ttyd process        tmux session
   (port 7681+N)   ──  vibecode-claude-*
                      vibecode-codex-*
                      vibecode-bash-*
                        │
                        ▼
                claude / codex / bash
```

**Vibecode khác MyCode ở chỗ nào:**

| Vibecode (hiện tại) | MyCode (mục tiêu) |
|---|---|
| `capture-pane` mỗi 2s → render `<pre>` | **Terminal thật** (xterm.js qua ttyd) realtime |
| Nút Enter/Up/Down mô phỏng | Gõ trực tiếp từ bàn phím |
| Không scroll-back | Scroll-back đầy đủ của xterm |
| Một session một lúc | Multi-tab, đổi session không mất state |
| Không theme | Theme switcher (dark/solarized/dracula) |
| Không upload file | File browser + upload/download |
| Mobile: wrap gãy layout | Mobile: keyboard toolbar (Esc/Tab/Ctrl/arrow) |

---

## 1. Prerequisites

### 1.1. Hệ thống
- [ ] Linux x86_64 (đã có trong env)
- [ ] Python 3.12+ (`python3 --version`)
- [ ] tmux 3.x (`tmux -V`)
- [ ] Caddy đã chạy trong container `cliproxy-caddy` (đã có)
- [ ] Port `8770` (app), `7681-7781` (ttyd pool) free

### 1.2. Cài ttyd
ttyd chưa được cài. Dùng static binary (dễ nhất, không cần build):

```bash
# Download static binary
mkdir -p /usr/local/bin
curl -fsSL -o /usr/local/bin/ttyd \
  https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64
chmod +x /usr/local/bin/ttyd
ttyd --version
```

- [ ] `ttyd --version` in ra version 1.7.x
- [ ] `which ttyd` → `/usr/local/bin/ttyd`

> **Lưu ý:** Nếu curl fail (no internet trong sandbox), fallback dùng `pip install ttyd` **KHÔNG có** — phải build từ source hoặc dùng docker image `tsl0922/ttyd`. Ghi chú trong README nếu không cài được.

### 1.3. Python deps
Dùng stdlib-first (giống vibecode). Chỉ thêm nếu thực sự cần:

```bash
# Option A: stdlib only (http.server) — ưu tiên
# Option B: Flask (nếu cần middleware, đơn giản hơn)
pip install flask==3.0.0
```

- [ ] Chọn stack: **stdlib** (default) hoặc **Flask** (nếu routing phức tạp)

---

## 2. Cấu trúc thư mục

```
/mycode/
├── app.py                    # Main server (port 8770)
├── ttyd_manager.py           # Spawn/kill ttyd processes
├── tmux_manager.py           # tmux session CRUD + monitor
├── registry.py               # Session registry JSON I/O
├── auth.py                   # Token-based auth
├── monitor.py                # Auto-approve monitor loop
├── config.py                 # Env var + defaults
│
├── static/
│   ├── dashboard.html        # Landing: grid of session cards + launcher
│   ├── viewer.html           # Terminal viewer wrapping ttyd iframe
│   ├── files.html            # File browser (optional phase 5)
│   ├── css/
│   │   ├── base.css
│   │   ├── dashboard.css
│   │   └── viewer.css
│   └── js/
│       ├── dashboard.js
│       ├── viewer.js
│       └── mobile-toolbar.js # Keyboard helper for mobile
│
├── data/
│   ├── registry.json         # Active sessions list
│   └── tokens.json           # Auth tokens
│
├── logs/
│   └── mycode.log
│
├── scripts/
│   ├── redeploy.sh
│   └── install-ttyd.sh
│
├── pland.md                  # This file
├── README.md
└── CHANGELOG.md
```

- [ ] Tạo đủ thư mục bằng:
  ```bash
  cd /mycode
  mkdir -p static/{css,js} data logs scripts
  touch static/dashboard.html static/viewer.html
  touch data/registry.json data/tokens.json
  echo '{"sessions":[]}' > data/registry.json
  echo '{"tokens":[]}' > data/tokens.json
  ```

---

## 3. Phase 1 — Bootstrap server (1-2h)

**Mục tiêu:** HTTP server chạy ở port 8770, serve dashboard HTML tĩnh, có health check.

### Task 1.1 — config.py
- [ ] Tạo [config.py](config.py) với các hằng số:
  ```python
  import os
  HOST = os.environ.get('MYCODE_HOST', '0.0.0.0')
  PORT = int(os.environ.get('MYCODE_PORT', '8770'))
  BASE_PATH = os.environ.get('MYCODE_BASE_PATH', '').rstrip('/')  # e.g. '/mycode'
  WORKSPACE = os.environ.get('MYCODE_WORKSPACE', '/root/.openclaw/workspace')
  DATA_DIR = os.environ.get('MYCODE_DATA', '/mycode/data')
  TTYD_BIN = os.environ.get('TTYD_BIN', '/usr/local/bin/ttyd')
  TTYD_PORT_START = int(os.environ.get('TTYD_PORT_START', '7681'))
  TTYD_PORT_END = int(os.environ.get('TTYD_PORT_END', '7781'))
  MONITOR_INTERVAL_SEC = int(os.environ.get('MYCODE_MONITOR_INTERVAL', '5'))
  SESSION_PREFIX = 'mycode'  # tmux session name prefix
  ```

- [ ] **Done when:** `python3 -c "import config; print(config.PORT)"` in ra `8770`.

### Task 1.2 — app.py boilerplate
- [ ] Tạo [app.py](app.py) dùng `http.server.ThreadingHTTPServer`:
  ```python
  from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
  from pathlib import Path
  import json, config
  
  STATIC_DIR = Path(__file__).parent / 'static'
  
  class Handler(BaseHTTPRequestHandler):
      def do_GET(self):
          path = self.path.split('?')[0]
          if config.BASE_PATH and path.startswith(config.BASE_PATH):
              path = path[len(config.BASE_PATH):] or '/'
          if path == '/' or path == '/dashboard':
              self._serve_file('dashboard.html', 'text/html')
          elif path == '/health':
              self._json({'ok': True})
          elif path.startswith('/static/'):
              fp = STATIC_DIR / path[len('/static/'):]
              if fp.exists() and fp.is_file():
                  ct = self._ctype(fp.suffix)
                  self._serve_file(fp.relative_to(STATIC_DIR), ct, raw=True)
              else:
                  self.send_error(404)
          else:
              self.send_error(404)
      
      def _serve_file(self, rel, ctype, raw=False):
          fp = STATIC_DIR / rel if not raw else STATIC_DIR / rel
          data = fp.read_bytes()
          # Inject BASE_PATH vào HTML nếu cần
          if ctype == 'text/html':
              data = data.replace(b'__BASE__', config.BASE_PATH.encode())
          self.send_response(200)
          self.send_header('Content-Type', ctype)
          self.send_header('Content-Length', str(len(data)))
          self.end_headers()
          self.wfile.write(data)
      
      def _json(self, obj, code=200):
          body = json.dumps(obj).encode()
          self.send_response(code)
          self.send_header('Content-Type', 'application/json')
          self.send_header('Content-Length', str(len(body)))
          self.end_headers()
          self.wfile.write(body)
      
      @staticmethod
      def _ctype(suffix):
          return {'.html':'text/html','.css':'text/css','.js':'application/javascript',
                  '.json':'application/json','.svg':'image/svg+xml','.png':'image/png'}.get(suffix, 'application/octet-stream')
  
  if __name__ == '__main__':
      srv = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
      print(f'MyCode running on http://{config.HOST}:{config.PORT}{config.BASE_PATH}')
      srv.serve_forever()
  ```

- [ ] **Done when:** `python3 app.py` không crash, `curl http://localhost:8770/health` trả `{"ok": true}`.

### Task 1.3 — Dashboard placeholder
- [ ] Tạo [static/dashboard.html](static/dashboard.html) tối thiểu:
  ```html
  <!doctype html>
  <html><head><meta charset="utf-8"><title>MyCode</title>
  <link rel="stylesheet" href="__BASE__/static/css/base.css">
  <link rel="stylesheet" href="__BASE__/static/css/dashboard.css">
  </head>
  <body><div id="app"></div>
  <script>window.BASE_PATH='__BASE__';</script>
  <script src="__BASE__/static/js/dashboard.js"></script>
  </body></html>
  ```

- [ ] **Done when:** Mở http://localhost:8770/ thấy trang trắng, DevTools không có lỗi 404.

### Task 1.4 — Caddy route
- [ ] Thêm route `/mycode/*` vào Caddy config (container `cliproxy-caddy`):
  ```caddy
  handle_path /mycode/* {
      reverse_proxy localhost:8770
  }
  handle_path /mycode/tty/* {
      reverse_proxy localhost:7681  # sẽ fix dynamic ở phase 3
  }
  ```
- [ ] Reload Caddy: `docker exec cliproxy-caddy caddy reload --config /etc/caddy/Caddyfile`
- [ ] **Done when:** `curl https://<domain>/mycode/health` → `{"ok": true}`.

---

## 4. Phase 2 — tmux session manager (2-3h)

**Mục tiêu:** CRUD cho tmux sessions (`mycode-claude-*`, `mycode-codex-*`, `mycode-bash-*`). Không cần ttyd ở bước này.

### Task 2.1 — tmux_manager.py
- [ ] Tạo [tmux_manager.py](tmux_manager.py):
  ```python
  import subprocess, re, time, uuid
  from config import SESSION_PREFIX
  
  ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
  
  def tmux(*args, check=False, timeout=5):
      return subprocess.run(['tmux', *args], capture_output=True, text=True, timeout=timeout, check=check)
  
  def generate_name(kind: str) -> str:
      return f"{SESSION_PREFIX}-{kind}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
  
  def create(name: str, cmd: str, cols=120, rows=40):
      r = tmux('new-session', '-d', '-s', name, '-x', str(cols), '-y', str(rows), 'bash', '-lc', cmd)
      return r.returncode == 0, r.stderr
  
  def exists(name: str) -> bool:
      return tmux('has-session', '-t', name).returncode == 0
  
  def capture(name: str, history_lines=30) -> str:
      r = tmux('capture-pane', '-t', name, '-p', '-S', f'-{history_lines}')
      return ANSI_RE.sub('', r.stdout) if r.returncode == 0 else ''
  
  def send_text(name: str, text: str):
      tmux('send-keys', '-t', name, text)
      time.sleep(0.15)
      tmux('send-keys', '-t', name, 'Enter')
  
  def send_key(name: str, key: str):
      tmux('send-keys', '-t', name, key)
  
  def kill(name: str):
      tmux('kill-session', '-t', name)
  
  def list_all():
      r = tmux('list-sessions', '-F', '#{session_name}')
      if r.returncode != 0: return []
      return [n for n in r.stdout.strip().split('\n') if n.startswith(SESSION_PREFIX + '-')]
  ```

- [ ] **Done when:** Test manually:
  ```python
  import tmux_manager as t
  n = t.generate_name('bash')
  t.create(n, 'bash')
  assert t.exists(n)
  t.send_text(n, 'echo hello')
  time.sleep(0.3)
  assert 'hello' in t.capture(n)
  t.kill(n)
  ```

### Task 2.2 — registry.py
- [ ] Tạo [registry.py](registry.py) với file locking (stdlib `fcntl`):
  ```python
  import json, fcntl, os
  from pathlib import Path
  from config import DATA_DIR
  
  REG_PATH = Path(DATA_DIR) / 'registry.json'
  
  def load():
      REG_PATH.parent.mkdir(parents=True, exist_ok=True)
      if not REG_PATH.exists():
          REG_PATH.write_text('{"sessions":[]}')
      with open(REG_PATH) as f:
          fcntl.flock(f, fcntl.LOCK_SH)
          data = json.load(f)
      return data
  
  def save(data):
      tmp = REG_PATH.with_suffix('.tmp')
      with open(tmp, 'w') as f:
          fcntl.flock(f, fcntl.LOCK_EX)
          json.dump(data, f, indent=2)
      os.replace(tmp, REG_PATH)
  
  def add_session(entry: dict):
      data = load()
      data['sessions'] = [s for s in data['sessions'] if s['name'] != entry['name']]
      data['sessions'].append(entry)
      save(data)
  
  def remove_session(name: str):
      data = load()
      data['sessions'] = [s for s in data['sessions'] if s['name'] != name]
      save(data)
  
  def get(name: str):
      return next((s for s in load()['sessions'] if s['name'] == name), None)
  ```

- [ ] Schema mỗi session:
  ```json
  {
    "name": "mycode-claude-1714000000-abc123",
    "kind": "claude",
    "title": "Claude - task X",
    "cmd": "claude",
    "ttyd_port": 7681,
    "created_at": 1714000000,
    "auto_approve": false,
    "token": "hex-32-chars"
  }
  ```

- [ ] **Done when:** `registry.add_session({...}); registry.get(name)` trả đúng entry.

### Task 2.3 — API endpoints (chưa có ttyd)
- [ ] Mở rộng `Handler.do_POST` trong [app.py](app.py):
  - `POST /api/sessions` — tạo tmux session + registry entry
  - `GET /api/sessions` — list
  - `DELETE /api/sessions/{name}` — kill + remove
  - `POST /api/sessions/{name}/keys` — send keys (body `{"key":"Enter"}` hoặc `{"text":"ls"}`)

  ```python
  def do_POST(self):
      path = self._strip_base(self.path)
      length = int(self.headers.get('Content-Length', 0))
      body = json.loads(self.rfile.read(length) or b'{}')
      if path == '/api/sessions':
          kind = body.get('kind', 'bash')
          cmd = {'claude':'claude','codex':'codex','bash':'bash'}.get(kind, 'bash')
          name = tmux_manager.generate_name(kind)
          ok, err = tmux_manager.create(name, cmd)
          if not ok: return self._json({'error': err}, 500)
          entry = {'name':name,'kind':kind,'cmd':cmd,'created_at':int(time.time()),
                   'auto_approve':False,'token':secrets.token_hex(16)}
          registry.add_session(entry)
          return self._json(entry)
      # ... more
  ```

- [ ] **Done when:** `curl -XPOST http://localhost:8770/api/sessions -d '{"kind":"bash"}'` trả entry, `tmux ls` thấy session mới.

---

## 5. Phase 3 — ttyd integration (3-4h) ⭐ Core

**Mục tiêu:** Mỗi session có một ttyd process riêng attach vào tmux session, phục vụ qua WebSocket.

### Task 3.1 — ttyd_manager.py
- [ ] Tạo [ttyd_manager.py](ttyd_manager.py):
  ```python
  import subprocess, socket, secrets, os, signal
  from config import TTYD_BIN, TTYD_PORT_START, TTYD_PORT_END
  
  _processes = {}  # session_name -> (Popen, port)
  
  def _find_free_port():
      for port in range(TTYD_PORT_START, TTYD_PORT_END + 1):
          with socket.socket() as s:
              try:
                  s.bind(('127.0.0.1', port))
                  return port
              except OSError:
                  continue
      raise RuntimeError('No free port in ttyd pool')
  
  def start(session_name: str, token: str) -> int:
      """Spawn ttyd attached to existing tmux session. Returns port."""
      port = _find_free_port()
      # ttyd flags:
      #   -p port
      #   -i 127.0.0.1 (only local, Caddy proxies)
      #   -t disableLeaveAlert=true -t fontSize=14
      #   -W (writable)
      #   -c user:token (basic auth) OR -o (one-shot) — dùng token URL param
      #   --url-arg (cho phép token qua URL)
      args = [TTYD_BIN,
              '-p', str(port),
              '-i', '127.0.0.1',
              '-W',
              '-t', 'disableLeaveAlert=true',
              '-t', 'fontSize=14',
              '-t', 'theme={"background":"#0a0f1d","foreground":"#e4e9f5"}',
              '-c', f'mycode:{token}',
              'tmux', 'attach', '-t', session_name]
      proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              preexec_fn=os.setsid)
      _processes[session_name] = (proc, port)
      return port
  
  def stop(session_name: str):
      entry = _processes.pop(session_name, None)
      if entry:
          proc, _ = entry
          try:
              os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
          except ProcessLookupError:
              pass
  
  def port_of(session_name: str):
      e = _processes.get(session_name)
      return e[1] if e else None
  ```

- [ ] **Done when:**
  - `ttyd_manager.start('test-session', 'abc')` trả port 7681+
  - `curl -u mycode:abc http://127.0.0.1:7681/` trả HTML của ttyd
  - `ttyd_manager.stop('test-session')` không còn process `ttyd`

### Task 3.2 — Wire vào API create/delete
- [ ] Trong handler `POST /api/sessions`:
  ```python
  ok, err = tmux_manager.create(name, cmd)
  port = ttyd_manager.start(name, token)
  entry['ttyd_port'] = port
  ```
- [ ] Trong `DELETE /api/sessions/{name}`:
  ```python
  ttyd_manager.stop(name)
  tmux_manager.kill(name)
  registry.remove_session(name)
  ```

### Task 3.3 — Reverse proxy ttyd qua app.py (tránh cần Caddy dynamic)
Có 2 lựa chọn, **chọn B** để đơn giản:

**A.** Mỗi ttyd port expose riêng qua Caddy → phải reload Caddy mỗi lần tạo session → phức tạp.

**B.** ✅ app.py làm reverse proxy `/tty/{name}` → `127.0.0.1:{port}` (cả HTTP + WebSocket upgrade).

- [ ] Implement WebSocket proxy trong app.py dùng `websockets` lib hoặc `asyncio` raw sockets. Cách nhẹ nhất: **dùng Flask + flask-sock + httpx** hoặc **aiohttp**:
  ```bash
  pip install aiohttp
  ```
  
  Refactor app.py → `aiohttp.web`:
  ```python
  from aiohttp import web, WSMsgType, ClientSession
  
  async def proxy_tty(request):
      name = request.match_info['name']
      port = ttyd_manager.port_of(name)
      if not port:
          return web.Response(status=404, text='session not found')
      tail = request.match_info['tail']
      upstream = f'http://127.0.0.1:{port}/{tail}'
      if request.headers.get('Upgrade', '').lower() == 'websocket':
          return await _proxy_ws(request, upstream.replace('http', 'ws'))
      async with ClientSession() as s:
          async with s.request(request.method, upstream, headers=request.headers,
                               data=await request.read()) as r:
              body = await r.read()
              return web.Response(status=r.status, body=body, headers=r.headers)
  
  async def _proxy_ws(request, upstream_url):
      ws_client = web.WebSocketResponse(protocols=['tty'])
      await ws_client.prepare(request)
      async with ClientSession() as s:
          async with s.ws_connect(upstream_url, protocols=['tty']) as ws_up:
              async def c2u():
                  async for m in ws_client:
                      if m.type == WSMsgType.TEXT: await ws_up.send_str(m.data)
                      elif m.type == WSMsgType.BINARY: await ws_up.send_bytes(m.data)
              async def u2c():
                  async for m in ws_up:
                      if m.type == WSMsgType.TEXT: await ws_client.send_str(m.data)
                      elif m.type == WSMsgType.BINARY: await ws_client.send_bytes(m.data)
              await asyncio.gather(c2u(), u2c())
      return ws_client
  
  app = web.Application()
  app.router.add_route('*', '/tty/{name}/{tail:.*}', proxy_tty)
  ```

- [ ] **Done when:** Trong browser mở `http://localhost:8770/tty/<session>/` thấy terminal ttyd (Basic auth dùng token).

### Task 3.4 — Viewer HTML embed ttyd
- [ ] Tạo [static/viewer.html](static/viewer.html):
  ```html
  <!doctype html><html><head><meta charset="utf-8"><title>Terminal</title>
  <link rel="stylesheet" href="__BASE__/static/css/viewer.css"></head>
  <body>
    <header class="top-bar">
      <a href="__BASE__/">← Back</a>
      <span id="session-title"></span>
      <div class="actions">
        <button id="auto-approve-btn">Auto-approve: OFF</button>
        <button id="kill-btn">Kill</button>
      </div>
    </header>
    <iframe id="term" src=""></iframe>
    <div id="mobile-toolbar"></div>
    <script>window.BASE_PATH='__BASE__';</script>
    <script src="__BASE__/static/js/viewer.js"></script>
    <script src="__BASE__/static/js/mobile-toolbar.js"></script>
  </body></html>
  ```

- [ ] [static/js/viewer.js](static/js/viewer.js):
  ```js
  const name = new URLSearchParams(location.search).get('s');
  const token = new URLSearchParams(location.search).get('t');
  document.getElementById('term').src =
    `${BASE_PATH}/tty/${name}/?arg=mycode:${token}`;  // or URL-embedded basic auth
  ```

- [ ] **Done when:** Từ dashboard click vào session → viewer.html hiển thị terminal tương tác được (gõ `ls` thấy output).

---

## 6. Phase 4 — Dashboard UX (2-3h)

**Mục tiêu:** UI đẹp, tạo session 1 click, multi-tab, trạng thái realtime.

### Task 4.1 — Dashboard layout
- [ ] [static/js/dashboard.js](static/js/dashboard.js): render grid các app card (Claude / Codex / Bash / Custom):
  ```js
  const APPS = [
    {kind:'claude', label:'Claude Code', icon:'claude.svg', bg:'linear-gradient(135deg,#e8640e,#c94207)'},
    {kind:'codex',  label:'Codex',       icon:'codex.svg',  bg:'#0d0d0d'},
    {kind:'bash',   label:'Terminal',    icon:'bash.svg',   bg:'linear-gradient(135deg,#052e12,#0a1f0e)'},
  ];
  ```
- [ ] Below app grid: "Active sessions" section with cards showing:
  - Session title (editable)
  - Kind badge
  - Uptime
  - Auto-approve toggle
  - Open / Kill buttons

### Task 4.2 — Session polling (cheap, chỉ status không phải content)
- [ ] `GET /api/sessions` mỗi 5s → update cards.

### Task 4.3 — Multi-tab
- [ ] Dùng localStorage lưu danh sách tabs đang mở:
  ```js
  // Trong viewer: mỗi tab là một <iframe> trong <div class="tabs">
  // Dùng thư viện nhẹ như <tab-bar> custom element, không cần React
  ```

### Task 4.4 — Theme switcher
- [ ] Persist `theme` trong localStorage, 3 theme: dark / solarized / dracula.
- [ ] Truyền vào ttyd qua query `?arg=-t theme=...` — hoặc restart ttyd process với theme mới khi switch.

### Task 4.5 — Mobile keyboard toolbar
- [ ] [static/js/mobile-toolbar.js](static/js/mobile-toolbar.js): khi `window.innerWidth < 768`, hiện toolbar fixed bottom gồm `Esc | Tab | Ctrl | ↑ | ↓ | ← | →`.
- [ ] Gửi key vào iframe ttyd qua `postMessage`. Nếu ttyd không hỗ trợ, fallback: gọi `POST /api/sessions/{name}/keys`.

---

## 7. Phase 5 — Auto-approve monitor (1-2h)

Port từ vibecode với cải tiến: detection tốt hơn, rate-limit per session, log action.

### Task 5.1 — monitor.py
- [ ] Tạo [monitor.py](monitor.py) chạy trong thread riêng:
  ```python
  import threading, time, re
  import registry, tmux_manager
  
  APPROVE_PATTERNS = [
      r'\by/n\b', r'\(y/n\)', r'\(y\)',
      r'do you want to proceed', r'approve', r'allow (once|always|this|claude|it)',
      r'press enter', r'waiting for',
  ]
  NUMBERED_PAT = re.compile(r'^\s*[❯>]\s*1\.|\b1\.\s+yes\b|\b1\)\s+yes\b', re.M)
  YN_PAT = re.compile(r'\by/n\b|\(y/n\)|\(y\)', re.I)
  
  def classify(text: str) -> str | None:
      low = text.lower()
      if not any(re.search(p, low) for p in APPROVE_PATTERNS): return None
      if YN_PAT.search(low): return 'y'
      if NUMBERED_PAT.search(text): return '1'
      return 'enter'
  
  def approve(session_name: str):
      content = tmux_manager.capture(session_name, 30)
      action = classify(content)
      if not action: return False
      if action == 'y':   tmux_manager.send_key(session_name, 'y')
      elif action == '1': tmux_manager.send_key(session_name, '1')
      time.sleep(0.2)
      tmux_manager.send_key(session_name, 'Enter')
      return True
  
  def loop():
      while True:
          try:
              for s in registry.load()['sessions']:
                  if s.get('auto_approve'): approve(s['name'])
          except Exception as e:
              print('[monitor]', e)
          time.sleep(5)
  
  def start():
      t = threading.Thread(target=loop, daemon=True); t.start()
  ```

- [ ] Gọi `monitor.start()` khi app startup.
- [ ] **Done when:** Tạo session claude với auto_approve=true, khi claude hỏi approve, tự động gửi y/enter trong 5s.

### Task 5.2 — API toggle
- [ ] `POST /api/sessions/{name}/auto-approve` body `{"enabled":true}` → update registry.

---

## 8. Phase 6 — File browser (optional, 2-3h)

### Task 6.1 — Backend
- [ ] `GET /api/files?path=/root/...` → list children với name, size, mtime, is_dir
- [ ] `GET /api/files/content?path=...` → file content (text) hoặc 400 nếu binary
- [ ] `POST /api/files/upload` multipart → lưu vào WORKSPACE
- [ ] **Security:** path traversal protection, chỉ cho phép paths dưới `WORKSPACE`

### Task 6.2 — Frontend
- [ ] Sidebar toggle, tree view collapsible, drag-drop upload
- [ ] Click text file → mở tab viewer đơn giản (read-only, optional: Monaco editor)

---

## 9. Phase 7 — Auth & hardening (1h)

### Task 7.1 — Token auth
- [ ] `POST /api/login` body `{"password":"..."}` check env `MYCODE_PASSWORD`, trả session cookie (HMAC-signed).
- [ ] Middleware decorator `@require_auth` cho tất cả `/api/*` và `/tty/*`.
- [ ] **Done when:** Không login không xem được session nào.

### Task 7.2 — Per-session token
- [ ] URL viewer dùng token riêng: `/viewer?s=<name>&t=<token>`. Token check trước khi proxy tới ttyd.
- [ ] Rate limit: max 5 login fail/phút per IP.

### Task 7.3 — Logging
- [ ] Ghi log có timestamp vào `logs/mycode.log`: session create/kill, auto-approve actions, auth events.

---

## 10. Phase 8 — Deploy scripts (30 phút)

### Task 8.1 — scripts/redeploy.sh
- [ ] ```bash
  #!/bin/bash
  cd /mycode
  kill $(lsof -ti :8770) 2>/dev/null
  # Kill ttyd pool
  for p in $(seq 7681 7781); do kill $(lsof -ti :$p) 2>/dev/null; done
  sleep 1
  MYCODE_BASE_PATH=/mycode python3 app.py >> logs/mycode.log 2>&1 &
  sleep 1
  curl -s http://localhost:8770/health && echo " OK"
  ```
- [ ] `chmod +x scripts/redeploy.sh`

### Task 8.2 — README.md
- [ ] Include: install ttyd, caddy config snippet, env vars, common commands, troubleshooting (`Unexpected token '<'` = thiếu `MYCODE_BASE_PATH`).

---

## 11. Phase 9 — Tests (nice-to-have)

- [ ] `tests/test_tmux_manager.py` — create/send/capture/kill
- [ ] `tests/test_registry.py` — add/remove/locking
- [ ] `tests/test_monitor.py` — classify() với fixture strings
- [ ] `tests/integration/test_session_lifecycle.sh` — curl end-to-end

---

## 12. Final checklist (trước khi kết thúc)

- [ ] Dashboard load < 500ms, không lỗi 404 trong DevTools
- [ ] Tạo session Claude → mở viewer → gõ lệnh → thấy realtime (< 100ms latency)
- [ ] Đóng tab browser → reopen → session còn, content không mất (tmux persistence)
- [ ] Mobile (< 768px): keyboard toolbar hiện, gõ vẫn được
- [ ] Auto-approve: enable → claude hỏi → tự động approve trong 5-10s
- [ ] Kill session từ UI → tmux ls không còn, ttyd process killed
- [ ] Reload Caddy, vẫn work qua `https://.../mycode/`
- [ ] Redeploy 3 lần liên tiếp không lỗi port busy

---

## 13. Bài học rút từ vibecode (phải tránh)

1. **Thiếu BASE_PATH env** → JS gọi sai endpoint → lỗi `Unexpected token '<'`. **Fix:** luôn inject `window.BASE_PATH` + validate lúc startup.
2. **tmux default width 220 cols** → TUI vỡ. **Fix:** `-x 120 -y 40` cố định, configurable qua env.
3. **`white-space: pre` trên mobile** → scroll ngang xấu. **Fix:** media query `pre-wrap` ở < 768px. (MyCode dùng xterm.js thật nên không gặp.)
4. **Polling 2s** → lag + tốn CPU. **Fix:** ttyd dùng WebSocket, realtime không polling.
5. **Send-keys text+Enter quá nhanh** → Codex miss Enter. **Fix:** sleep 150ms giữa text và Enter.
6. **Stale tmux session sau crash** → không list được. **Fix:** lúc startup, reconcile registry vs `tmux list-sessions`, drop entries không còn.
7. **No auth** → ai biết URL cũng vào được. **Fix:** token + cookie bắt buộc từ đầu.

---

## 14. Ước lượng thời gian

| Phase | Ước lượng | Ưu tiên |
|---|---|---|
| 1. Bootstrap | 1-2h | P0 |
| 2. tmux manager | 2-3h | P0 |
| 3. ttyd integration | 3-4h | P0 ⭐ |
| 4. Dashboard UX | 2-3h | P1 |
| 5. Auto-approve | 1-2h | P1 |
| 6. File browser | 2-3h | P2 |
| 7. Auth | 1h | P1 |
| 8. Deploy scripts | 30min | P0 |
| 9. Tests | 1-2h | P2 |
| **Total (P0+P1)** | **11-16h** | |

---

## 15. Quy tắc làm việc cho LLM

1. **Làm theo thứ tự Phase.** Không nhảy cóc Phase 3 trước khi Phase 2 xong.
2. **Test sau mỗi Task.** Mỗi task có "Done when…" — phải verify.
3. **Không refactor ngoài scope.** Task chỉ thêm 1 endpoint thì không rewrite cả file.
4. **Commit theo Phase.** `git commit -m "phase 2: tmux manager + registry"`.
5. **Log lại quyết định** trong CHANGELOG.md nếu lệch plan (vd: chọn aiohttp thay vì stdlib).
6. **Khi bug, đọc vibecode/app.py** để tham khảo — không copy-paste, hiểu rồi viết lại.
7. **Đụng lỗi 3 lần cùng pattern → dừng lại, báo user, đừng tự fix loạn.**

---

_Kết thúc plan. Bắt đầu từ Task 1.1._
