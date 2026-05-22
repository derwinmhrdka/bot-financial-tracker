"""Muat .env.local dari root project ke os.environ."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"


def load_env_local() -> bool:
    if not _ENV_FILE.exists():
        return False
    raw = _ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value
    return True
