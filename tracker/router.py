"""Routing pesan Telegram → track.py (tanpa LLM)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tracker.parse import extract_amount

_REPO = Path(__file__).resolve().parent.parent

_MONTH_WORDS: dict[str, str] = {
    "januari": "JANUARY",
    "februari": "FEBRUARY",
    "maret": "MARCH",
    "april": "APRIL",
    "mei": "MAY",
    "juni": "JUNE",
    "juli": "JULY",
    "agustus": "AUGUST",
    "september": "SEPTEMBER",
    "oktober": "OCTOBER",
    "november": "NOVEMBER",
    "desember": "DECEMBER",
    "january": "JANUARY",
    "february": "FEBRUARY",
    "march": "MARCH",
    "may": "MAY",
    "june": "JUNE",
    "july": "JULY",
    "august": "AUGUST",
    "october": "OCTOBER",
    "december": "DECEMBER",
}


def _telegram_user_id(user_id: int) -> str:
    """ID pengguna Telegram (bukan ID grup)."""
    return f"telegram:{user_id}"


def _invoke(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(_REPO / "track.py"), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO),
        env=os.environ.copy(),
    )
    out = (proc.stdout or "").strip()
    if not out:
        err = (proc.stderr or "").strip() or "Perintah gagal"
        return proc.returncode or 1, f"❌ {err[:200]}"
    try:
        data = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return 1, "❌ Respons CLI tidak valid"
    return proc.returncode, str(data.get("telegram_reply") or data.get("error") or "OK")


def normalize_telegram_text(text: str) -> str:
    """Buang /command dan @suffix bot (mis. /help@MyBot → help)."""
    raw = (text or "").strip()
    if raw.startswith("/"):
        raw = raw[1:].split("@", 1)[0].strip()
    return raw


def _month_from_text(text: str) -> str | None:
    lower = text.lower()
    for word, sheet in _MONTH_WORDS.items():
        if word in lower:
            return sheet
    return None


def is_tracker_message(text: str) -> bool:
    """True jika pesan mirip perintah tracker (untuk filter chat grup)."""
    raw = normalize_telegram_text(text)
    if not raw:
        return False

    lower = raw.lower()

    if lower in ("start", "help", "bantuan", "h", "?", "new", "reset"):
        return True

    if lower in (
        "list user",
        "daftar user",
        "users",
        "list users",
        "daftar pengguna",
        "help admin",
        "bantuan admin",
    ):
        return True
    if re.search(r"\b(?:tambah|add|daftar)\s+user\s+\d+", lower):
        return True
    if re.search(r"\b(?:hapus|remove|keluarkan|delete)\s+user\s+\d+", lower):
        return True

    if re.search(r"\bundo\b", lower) and not re.search(r"hapus|delete", lower):
        return True
    if re.search(r"(?:hapus|delete)\s*#?\s*\d+", lower):
        return True
    if re.search(r"\b(pindah|transfer)\b", lower):
        return True
    if any(k in lower for k in ("sisa", "saldo")):
        return True
    if any(k in lower for k in ("total", "ringkasan", "summary", "rekap")):
        return True
    if lower.startswith("list") or "riwayat" in lower:
        return True
    if extract_amount(raw) or parse_message_candidate(raw):
        return True
    return False


def route_message(text: str, user_id: int) -> str:
    raw = normalize_telegram_text(text)
    if not raw:
        return "Kirim pengeluaran (mis. makan 35rb) atau: sisa daily, total, list, undo, help"

    lower = raw.lower()

    if lower in ("start", "help", "bantuan", "h", "?"):
        code, reply = _invoke(["help"])
        return reply

    if lower in ("new", "reset"):
        return "🔄 OK. Kirim transaksi atau perintah (sisa daily, total, list, undo)."

    uid = _telegram_user_id(user_id)
    month = _month_from_text(raw)

    if re.search(r"\bundo\b", lower) and not re.search(r"hapus|delete", lower):
        code, reply = _invoke(["undo", "--user-id", uid])
        return reply

    del_m = re.search(r"(?:hapus|delete)\s*#?\s*(\d+)", lower)
    if del_m:
        code, reply = _invoke(["delete", "--user-id", uid, "--id", del_m.group(1)])
        return reply

    if re.search(r"\b(pindah|transfer)\b", lower):
        code, reply = _invoke(["transfer", "--user-id", uid, "--text", raw])
        return reply

    if any(k in lower for k in ("sisa", "saldo")) and "pindah" not in lower:
        args = ["sisa", "--user-id", uid, "--text", raw]
        if month:
            args.extend(["--month", month])
        if "semua" in lower or re.search(r"\ball\b", lower):
            args.append("--all")
        code, reply = _invoke(args)
        return reply

    if any(k in lower for k in ("total", "ringkasan", "summary", "rekap")):
        args = ["summary", "--user-id", uid]
        if month and re.match(r"\d{4}-\d{2}", month):
            args.extend(["--month", month])
        code, reply = _invoke(args)
        return reply

    if lower.startswith("list") or "riwayat" in lower:
        limit = 10
        m = re.search(r"list\s*(\d+)", lower)
        if m:
            limit = max(1, min(50, int(m.group(1))))
        args = ["list", "--user-id", uid, "--limit", str(limit)]
        code, reply = _invoke(args)
        return reply

    if extract_amount(raw) or parse_message_candidate(raw):
        code, reply = _invoke(
            ["add", "--user-id", uid, "--text", raw, "--source", "telegram"]
        )
        return reply

    code, reply = _invoke(["help"])
    return reply + "\n\n💡 Contoh: makan 35rb · pindah daily ke entertain 100k · sisa daily · undo"


def parse_message_candidate(text: str) -> bool:
    from tracker.parse import parse_message

    return parse_message(text) is not None
