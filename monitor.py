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
            for s in registry.load().get('sessions', []):
                if s.get('auto_approve'): approve(s['name'])
        except Exception as e:
            print('[monitor]', e)
        time.sleep(5)

def start():
    t = threading.Thread(target=loop, daemon=True)
    t.start()
