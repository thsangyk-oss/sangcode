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

def scroll(name: str, direction: str, lines: int = 3):
    """Enter tmux copy-mode and scroll up/down. direction: 'up' | 'down'"""
    tmux('copy-mode', '-t', name)
    key = 'scroll-up' if direction == 'up' else 'scroll-down'
    for _ in range(lines):
        tmux('send-keys', '-t', name, '-X', key)
