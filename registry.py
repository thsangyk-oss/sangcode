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
