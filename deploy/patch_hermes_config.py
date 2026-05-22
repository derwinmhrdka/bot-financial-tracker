#!/usr/bin/env python3
"""Merge financial-tracker gateway settings into Hermes config.yaml."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    raise SystemExit(1)


def _load_env_local(repo: Path) -> dict[str, str]:
    env_file = repo / ".env.local"
    out: dict[str, str] = {}
    if not env_file.is_file():
        return out
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def patch_config(config_path: Path, repo_path: Path) -> None:
    raw = config_path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(raw) or {}
    repo_unix = repo_path.as_posix()

    skills = cfg.setdefault("skills", {})
    skills.setdefault("config", {}).setdefault("financial_tracker", {})[
        "repo_path"
    ] = repo_unix

    display = cfg.setdefault("display", {})
    display["tool_progress"] = "off"
    platforms = display.setdefault("platforms", {})
    tg_display = platforms.setdefault("telegram", {})
    if isinstance(tg_display, dict):
        tg_display["tool_progress"] = "off"

    agent = cfg.setdefault("agent", {})
    disabled = list(agent.get("disabled_toolsets") or [])
    if "skills" not in disabled:
        disabled.append("skills")
    agent["disabled_toolsets"] = disabled

    env = _load_env_local(repo_path)

    user_id = env.get("TELEGRAM_ALLOWED_USERS", "").split(",")[0].strip()
    if user_id:
        prompt = (
            "Financial tracker bot. WAJIB: jalankan `python "
            f"{repo_unix}/track.py` (bukan python -m tracker). "
            "Dilarang skill_view/skills_list. Balas user HANYA teks "
            "field telegram_reply dari JSON stdout."
        )
        tg = cfg.setdefault("telegram", {})
        prompts = tg.setdefault("channel_prompts", {}) or {}
        if not isinstance(prompts, dict):
            prompts = {}
        prompts[str(user_id)] = prompt
        tg["channel_prompts"] = prompts

    config_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> int:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    hermes = Path(
        os.environ.get("HERMES_HOME")
        or Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
    )
    config_path = hermes / "config.yaml"
    if not config_path.is_file():
        print(f"config.yaml tidak ada: {config_path}", file=sys.stderr)
        return 1
    patch_config(config_path, repo)
    print(f"Patched: {config_path}")
    print("  display.tool_progress: off")
    print("  agent.disabled_toolsets: +skills")
    print(f"  skills.config.financial_tracker.repo_path: {repo.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
