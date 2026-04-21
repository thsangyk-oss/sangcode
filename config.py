import os

HOST = os.environ.get('MYCODE_HOST', '0.0.0.0')
PORT = int(os.environ.get('MYCODE_PORT', '8770'))
BASE_PATH = os.environ.get('MYCODE_BASE_PATH', '').rstrip('/')  # e.g. '/mycode'
WORKSPACE = os.environ.get('MYCODE_WORKSPACE', '/root/.openclaw/workspace')
DATA_DIR = os.environ.get('MYCODE_DATA', '/root/mycode/data')
TTYD_BIN = os.environ.get('TTYD_BIN', '/usr/local/bin/ttyd')
TTYD_PORT_START = int(os.environ.get('TTYD_PORT_START', '7681'))
TTYD_PORT_END = int(os.environ.get('TTYD_PORT_END', '7781'))
MONITOR_INTERVAL_SEC = int(os.environ.get('MYCODE_MONITOR_INTERVAL', '5'))
SESSION_PREFIX = 'mycode'  # tmux session name prefix
