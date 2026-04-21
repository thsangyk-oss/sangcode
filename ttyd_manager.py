import subprocess, socket, os, signal, time
from config import TTYD_BIN, TTYD_PORT_START, TTYD_PORT_END

_processes = {}  # session_name -> (Popen, port)


def _port_listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(('127.0.0.1', port)) == 0


def _find_free_port():
    for port in range(TTYD_PORT_START, TTYD_PORT_END + 1):
        if _port_listening(port):
            continue
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError('No free port in ttyd pool')


def _kill_existing_ttyd_for_session(session_name: str):
    try:
        out = subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True)
    except Exception:
        return
    needle = f'tmux attach -t {session_name}'
    for line in out.splitlines():
        if TTYD_BIN in line and needle in line:
            try:
                pid = int(line.strip().split(None, 1)[0])
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                pass


def start(session_name: str, token: str) -> int:
    """Spawn ttyd attached to existing tmux session. Returns port.
    No -c (basic auth) because ttyd is only on 127.0.0.1, proxied through app.py which handles auth."""
    stop(session_name)
    _kill_existing_ttyd_for_session(session_name)
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
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            preexec_fn=os.setsid)
    _processes[session_name] = (proc, port)
    for _ in range(20):
        if _port_listening(port):
            return port
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    _processes.pop(session_name, None)
    raise RuntimeError(f'ttyd failed to start for {session_name}')


def stop(session_name: str):
    entry = _processes.pop(session_name, None)
    if entry:
        proc, _ = entry
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            pass


def stop_all():
    for name in list(_processes.keys()):
        stop(name)


def port_of(session_name: str):
    e = _processes.get(session_name)
    if not e:
        return None
    proc, port = e
    if proc.poll() is not None or not _port_listening(port):
        _processes.pop(session_name, None)
        return None
    return port
