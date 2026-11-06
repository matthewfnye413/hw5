"""Append-only audit trail: output/audit_trail.json.

The file is a JSON array. Every agent-loop step adds one entry; nothing is ever removed
or rewritten, and the file is never wiped between runs. If it can't be read (e.g. hand
edited into invalid JSON), it is set aside as audit_trail.corrupt-<time>.json and a new
file starts, so no history is silently lost.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from backend.models import AuditEntry

ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = Path(os.environ.get("CAMPUS_AUDIT", ROOT / "output" / "audit_trail.json"))
_lock = threading.Lock()


def _load() -> list:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json"))
    return []


def append(entry: AuditEntry) -> None:
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = _load()
        data.append(entry.model_dump(mode="json"))
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)  # atomic: a crash never leaves half a file


def count() -> int:
    with _lock:
        return len(_load())
