#!/usr/bin/env python3
"""Entry point — bisa dipanggil dari path absolut (Hermes terminal)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tracker.env import load_env_local
from tracker.cli import main

load_env_local()
raise SystemExit(main())
