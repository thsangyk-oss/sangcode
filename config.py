import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

HOST = os.environ.get('SANGCODE_HOST', '0.0.0.0')
PORT = int(os.environ.get('SANGCODE_PORT', '8770'))
BASE_PATH = os.environ.get('SANGCODE_BASE_PATH', '').rstrip('/')  # e.g. '/sangcode'
WORKSPACE = os.environ.get('SANGCODE_WORKSPACE', '/root')
DATA_DIR = os.environ.get('SANGCODE_DATA', str(ROOT_DIR / 'data'))
TTYD_BIN = os.environ.get('TTYD_BIN', '/usr/local/bin/ttyd')
TTYD_PORT_START = int(os.environ.get('TTYD_PORT_START', '7681'))
TTYD_PORT_END = int(os.environ.get('TTYD_PORT_END', '7781'))
MONITOR_INTERVAL_SEC = int(os.environ.get('SANGCODE_MONITOR_INTERVAL', '5'))
SESSION_PREFIX = os.environ.get('SANGCODE_SESSION_PREFIX', 'mycode')
LEGACY_SESSION_PREFIXES = [
    prefix.strip()
    for prefix in os.environ.get('SANGCODE_LEGACY_SESSION_PREFIXES', 'sangcode').split(',')
    if prefix.strip() and prefix.strip() != SESSION_PREFIX
]
