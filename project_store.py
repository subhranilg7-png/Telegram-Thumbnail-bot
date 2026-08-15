import json, os, uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECTS_DIR = ROOT / 'projects'
PROJECTS_DIR.mkdir(exist_ok=True)


def new_project(data: dict[str, Any]) -> str:
    pid = uuid.uuid4().hex[:12]
    data = dict(data)
    data['id'] = pid
    save_project(pid, data)
    return pid


def save_project(pid: str, data: dict[str, Any]):
    path = PROJECTS_DIR / f'{pid}.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def load_project(pid: str) -> dict[str, Any] | None:
    path = PROJECTS_DIR / f'{pid}.json'
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
