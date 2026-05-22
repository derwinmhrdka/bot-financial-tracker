"""Daftar pengguna Telegram yang boleh pakai bot (+ admin)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STORE = Path(__file__).resolve().parent.parent / "data" / "allowed_users.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_ids(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _load_raw() -> dict[str, Any]:
    if not _STORE.exists():
        return {"users": [], "admins": []}
    return json.loads(_STORE.read_text(encoding="utf-8"))


def _save_raw(data: dict[str, Any]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_loaded() -> None:
    """Buat file dari .env.local jika belum ada."""
    if _STORE.exists():
        return
    users = _parse_ids("TELEGRAM_ALLOWED_USERS")
    admins = _parse_ids("TELEGRAM_ADMIN_USERS") or users[:1]
    data = {
        "users": [{"id": uid, "added_at": _now(), "added_by": "env"} for uid in users],
        "admins": admins,
    }
    _save_raw(data)


def _user_ids(data: dict[str, Any]) -> set[str]:
    return {str(u["id"]) for u in data.get("users", [])}


def is_allowed(chat_id: int) -> bool:
    ensure_loaded()
    return str(chat_id) in _user_ids(_load_raw())


def is_admin(chat_id: int) -> bool:
    ensure_loaded()
    data = _load_raw()
    admins = {str(a) for a in data.get("admins", [])}
    if str(chat_id) in admins:
        return True
    # fallback env
    return str(chat_id) in set(_parse_ids("TELEGRAM_ADMIN_USERS"))


def list_users_text() -> str:
    ensure_loaded()
    data = _load_raw()
    admins = {str(a) for a in data.get("admins", [])}
    lines = ["👥 Pengguna terdaftar:", ""]
    for u in data.get("users", []):
        uid = str(u["id"])
        badge = " (admin)" if uid in admins else ""
        lines.append(f"• {uid}{badge}")
    if not data.get("users"):
        lines.append("(kosong)")
    return "\n".join(lines)


def add_user(target_id: str, *, by: int) -> tuple[bool, str]:
    ensure_loaded()
    target_id = target_id.strip()
    if not target_id.isdigit():
        return False, "❌ ID harus angka (dari @userinfobot)."

    data = _load_raw()
    if target_id in _user_ids(data):
        return False, f"ℹ️ User {target_id} sudah terdaftar."

    data["users"].append({"id": target_id, "added_at": _now(), "added_by": str(by)})
    _save_raw(data)
    return True, f"✅ User {target_id} ditambahkan."


def remove_user(target_id: str, *, by: int) -> tuple[bool, str]:
    ensure_loaded()
    target_id = target_id.strip()
    data = _load_raw()
    ids = _user_ids(data)
    admins = {str(a) for a in data.get("admins", [])}

    if target_id not in ids:
        return False, f"❌ User {target_id} tidak ada."

    if target_id in admins and len(admins) <= 1:
        return False, "❌ Tidak bisa hapus admin terakhir."

    if len(ids) <= 1:
        return False, "❌ Harus ada minimal satu user."

    data["users"] = [u for u in data["users"] if str(u["id"]) != target_id]
    if target_id in admins:
        data["admins"] = [a for a in data["admins"] if str(a) != target_id]
    _save_raw(data)
    return True, f"✅ User {target_id} dihapus."


def handle_admin_command(text: str, chat_id: int) -> str | None:
    """Perintah kelola user; return None jika bukan perintah admin."""
    if not is_admin(chat_id):
        return None

    raw = (text or "").strip()
    lower = raw.lower()

    if lower in ("list user", "daftar user", "users", "list users", "daftar pengguna"):
        return list_users_text()

    m = re.search(r"(?:tambah|add|daftar)\s+user\s+(\d+)", lower)
    if m:
        ok, msg = add_user(m.group(1), by=chat_id)
        return msg

    m = re.search(r"(?:hapus|remove|keluarkan|delete)\s+user\s+(\d+)", lower)
    if m:
        ok, msg = remove_user(m.group(1), by=chat_id)
        return msg

    if lower in ("help admin", "bantuan admin"):
        return (
            "🔐 Perintah admin:\n"
            "• tambah user 123456789\n"
            "• hapus user 123456789\n"
            "• list user"
        )

    return None
