from aiohttp import web, WSMsgType, ClientSession
from pathlib import Path
import json, time, secrets, asyncio, os, re
import config, tmux_manager, registry, ttyd_manager, monitor

STATIC_DIR = Path(__file__).parent / 'static'
ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')

def _json(obj, status=200):
    return web.json_response(obj, status=status)

def _strip_base(path):
    if config.BASE_PATH and path.startswith(config.BASE_PATH):
        return path[len(config.BASE_PATH):] or '/'
    return path

def _serve_html(filename):
    content = (STATIC_DIR / filename).read_text()
    content = content.replace('__BASE__', config.BASE_PATH)
    return web.Response(text=content, content_type='text/html')

# ── Auth Middleware ──
@web.middleware
async def auth_middleware(request, handler):
    path = _strip_base(request.path)
    # Always allow health check and static files
    if path == '/health' or path.startswith('/static/'):
        return await handler(request)
    # Allow ttyd proxy (has its own basic auth)
    if path.startswith('/tty/'):
        return await handler(request)

    pw = os.environ.get('MYCODE_PASSWORD')
    if pw:
        cookie = request.cookies.get('mycode_auth')
        if cookie != pw:
            if path.startswith('/api/'):
                return web.Response(status=401, text='Unauthorized')
            # Show password prompt
            return web.Response(
                status=401,
                text='<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MyCode Login</title>'
                     '<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:Inter,sans-serif;background:#0a0e1a;color:#f1f5f9;display:flex;align-items:center;justify-content:center;min-height:100vh}'
                     '.box{background:rgba(17,24,39,0.9);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;width:340px;text-align:center;backdrop-filter:blur(12px)}'
                     'h2{margin-bottom:8px;font-size:20px}p{color:#94a3b8;font-size:13px;margin-bottom:24px}'
                     'input{width:100%;padding:12px 16px;background:#0a0e1a;border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#f1f5f9;font-size:14px;outline:none;margin-bottom:16px}'
                     'input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,0.25)}'
                     'button{width:100%;padding:12px;background:#6366f1;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer}'
                     'button:hover{background:#818cf8}</style></head>'
                     '<body><div class="box"><h2>🔐 MyCode</h2><p>Enter password to continue</p>'
                     '<form onsubmit="event.preventDefault();document.cookie=\'mycode_auth=\'+document.getElementById(\'p\').value+\';path=/;max-age=31536000\';location.reload()">'
                     '<input type="password" id="p" placeholder="Password" autofocus>'
                     '<button type="submit">Login</button></form></div></body></html>',
                content_type='text/html')
    return await handler(request)

# ── Reconcile sessions on startup ──
def reconcile_sessions():
    """Remove registry entries for tmux sessions that no longer exist. Restart ttyd for alive ones."""
    data = registry.load()
    alive = []
    for s in data.get('sessions', []):
        if tmux_manager.exists(s['name']):
            # Restart ttyd for this session
            token = s.get('token', secrets.token_hex(16))
            try:
                port = ttyd_manager.start(s['name'], token)
                s['ttyd_port'] = port
            except Exception:
                pass
            s['is_running'] = True
            alive.append(s)
        # else: drop dead sessions
    data['sessions'] = alive
    registry.save(data)

# ── Path suggestion (like vibecode) ──
def suggest_paths(prefix, limit=30):
    raw = (prefix or '').strip()
    if not raw:
        raw = '/root'
    if not raw.startswith('/'):
        raw = '/' + raw

    root_real = os.path.realpath('/root')
    base_dir, needle = os.path.split(raw)
    if not base_dir:
        base_dir = '/'
    base_dir = os.path.realpath(base_dir)

    if base_dir != root_real and not base_dir.startswith(root_real + os.sep):
        return []
    if not os.path.isdir(base_dir):
        parent = os.path.dirname(base_dir)
        needle = os.path.basename(base_dir) + needle
        base_dir = parent
    if not os.path.isdir(base_dir):
        return []

    items = []
    try:
        for name in sorted(os.listdir(base_dir)):
            if name.startswith('.') and not needle.startswith('.'):
                continue
            if needle and not name.lower().startswith(needle.lower()):
                continue
            full = os.path.join(base_dir, name)
            if not os.path.isdir(full):
                continue
            items.append({'path': full, 'isDir': True})
            if len(items) >= limit:
                break
    except Exception:
        pass
    return items

# ── Routes ──
async def handle_get(request):
    path = _strip_base(request.path)
    query = request.query_string

    if path == '/' or path == '/dashboard':
        return _serve_html('dashboard.html')
    elif path == '/viewer':
        return _serve_html('viewer.html')
    elif path == '/health':
        return _json({'ok': True})
    elif path == '/api/sessions':
        data = registry.load()
        # Enrich with is_running
        for s in data.get('sessions', []):
            s['is_running'] = tmux_manager.exists(s['name'])
        return _json(data)
    elif path.startswith('/api/sessions/') and path.endswith('/capture'):
        name = path.split('/')[3]
        lines = int(request.query.get('lines', 200))
        text = tmux_manager.capture(name, history_lines=lines)
        return _json({'ok': True, 'text': text})
    elif path == '/api/path/suggest':
        prefix = request.query.get('prefix', '/root')
        items = suggest_paths(prefix)
        return _json({'ok': True, 'suggestions': items})
    elif path.startswith('/static/'):
        rel = path[len('/static/'):]
        fp = STATIC_DIR / rel
        if fp.exists() and fp.is_file():
            return web.FileResponse(fp)
    return web.Response(status=404, text='Not found')

async def handle_post(request):
    path = _strip_base(request.path)
    try:
        body = await request.json()
    except:
        body = {}

    if path == '/api/sessions':
        kind = body.get('kind', 'bash')
        workdir = body.get('workdir', '/root')
        cmd_map = {
            'claude': f'cd {workdir} && claude',
            'codex': f'cd {workdir} && codex',
            'opencode': f'cd {workdir} && opencode',
            'bash': f'cd {workdir} && bash'
        }
        cmd = cmd_map.get(kind, f'cd {workdir} && bash')
        name = tmux_manager.generate_name(kind)
        ok, err = tmux_manager.create(name, cmd)
        if not ok:
            return _json({'error': err}, status=500)

        token = secrets.token_hex(16)
        try:
            port = ttyd_manager.start(name, token)
        except Exception as e:
            tmux_manager.kill(name)
            return _json({'error': str(e)}, status=500)

        entry = {
            'name': name,
            'kind': kind,
            'cmd': cmd,
            'workdir': workdir,
            'created_at': int(time.time()),
            'auto_approve': False,
            'token': token,
            'ttyd_port': port,
            'is_running': True
        }
        registry.add_session(entry)
        return _json(entry)

    elif path.startswith('/api/sessions/') and path.endswith('/keys'):
        name = path.split('/')[3]
        if 'key' in body:
            tmux_manager.send_key(name, body['key'])
        elif 'text' in body:
            tmux_manager.send_text(name, body['text'])
        return _json({'ok': True})

    elif path.startswith('/api/sessions/') and path.endswith('/approve'):
        name = path.split('/')[3]
        content = tmux_manager.capture(name, 30)
        action = monitor.classify(content)
        if action:
            if action == 'y':
                tmux_manager.send_key(name, 'y')
            elif action == '1':
                tmux_manager.send_key(name, '1')
            await asyncio.sleep(0.2)
            tmux_manager.send_key(name, 'Enter')
            return _json({'ok': True, 'action': action})
        else:
            # Just send Enter as fallback
            tmux_manager.send_key(name, 'Enter')
            return _json({'ok': True, 'action': 'enter'})

    elif path.startswith('/api/sessions/') and path.endswith('/auto-approve'):
        name = path.split('/')[3]
        enabled = body.get('enabled', False)
        data = registry.load()
        for s in data.get('sessions', []):
            if s['name'] == name:
                s['auto_approve'] = enabled
        registry.save(data)
        return _json({'ok': True})

    elif path.startswith('/api/sessions/') and path.endswith('/scroll'):
        name = path.split('/')[3]
        direction = body.get('direction', 'up')   # 'up' or 'down'
        lines     = int(body.get('lines', 3))
        tmux_manager.scroll(name, direction, lines)
        return _json({'ok': True})

    return web.Response(status=404, text='Not found')

async def handle_delete(request):
    path = _strip_base(request.path)
    if path.startswith('/api/sessions/'):
        name = path.split('/')[3]
        ttyd_manager.stop(name)
        tmux_manager.kill(name)
        registry.remove_session(name)
        return _json({'ok': True})
    return web.Response(status=404)

# ── ttyd WebSocket Proxy ──
async def proxy_tty(request):
    name = request.match_info['name']
    port = ttyd_manager.port_of(name)
    if not port:
        return web.Response(status=404, text='session not found')
    tail = request.match_info.get('tail', '')
    qs = request.query_string
    upstream = f'http://127.0.0.1:{port}/{tail}'
    if qs:
        upstream += '?' + qs

    if request.headers.get('Upgrade', '').lower() == 'websocket':
        ws_url = upstream.replace('http://', 'ws://')
        return await _proxy_ws(request, ws_url)

    async with ClientSession() as s:
        fwd_headers = {}
        if 'Authorization' in request.headers:
            fwd_headers['Authorization'] = request.headers['Authorization']
        req_body = await request.read()
        async with s.request(request.method, upstream, headers=fwd_headers, data=req_body) as r:
            body = await r.read()
            if r.status == 200 and r.content_type == 'text/html':
                font_import = b"<style>@import url('https://fonts.googleapis.com/css?family=Fira+Code:400,500,600&subset=vietnamese,latin-ext&display=swap');</style></head>"
                body = body.replace(b'</head>', font_import)
            resp_headers = {}
            for k in ('Content-Type',):
                if k in r.headers:
                    resp_headers[k] = r.headers[k]
            return web.Response(status=r.status, body=body, headers=resp_headers)

async def _proxy_ws(request, upstream_url):
    ws_client = web.WebSocketResponse(protocols=['tty'])
    await ws_client.prepare(request)
    try:
        async with ClientSession() as s:
            async with s.ws_connect(upstream_url, protocols=['tty']) as ws_up:
                async def c2u():
                    async for m in ws_client:
                        if m.type == WSMsgType.TEXT:
                            await ws_up.send_str(m.data)
                        elif m.type == WSMsgType.BINARY:
                            await ws_up.send_bytes(m.data)
                        elif m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                            break
                async def u2c():
                    async for m in ws_up:
                        if m.type == WSMsgType.TEXT:
                            await ws_client.send_str(m.data)
                        elif m.type == WSMsgType.BINARY:
                            await ws_client.send_bytes(m.data)
                        elif m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                            break
                done, pending = await asyncio.wait(
                    [asyncio.ensure_future(c2u()), asyncio.ensure_future(u2c())],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
    except Exception as e:
        print(f'[ws-proxy] {e}')
    return ws_client

async def init_app():
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_route('*', '/tty/{name}/{tail:.*}', proxy_tty)
    app.router.add_route('GET', '/{tail:.*}', handle_get)
    app.router.add_route('POST', '/{tail:.*}', handle_post)
    app.router.add_route('DELETE', '/{tail:.*}', handle_delete)
    return app

if __name__ == '__main__':
    reconcile_sessions()
    monitor.start()
    print(f'MyCode running on http://{config.HOST}:{config.PORT}{config.BASE_PATH}')
    web.run_app(init_app(), host=config.HOST, port=config.PORT, print=None)
