import subprocess, socket, os, signal
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
    """Spawn ttyd attached to existing tmux session. Returns port.
    No -c (basic auth) because ttyd is only on 127.0.0.1, proxied through app.py which handles auth."""
    # Stop existing if any
    stop(session_name)
    port = _find_free_port()
    args = [TTYD_BIN,
            '-p', str(port),
            '-i', '127.0.0.1',
            '-W',
            '-t', 'disableLeaveAlert=true',
            '-t', 'fontSize=14',
            '-t', 'fontFamily="Fira Code", monospace',
            '-t', 'scrollback=10000',
            '-t', 'theme={"background":"#0a0f1d","foreground":"#e4e9f5"}',
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
