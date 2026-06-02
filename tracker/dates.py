"""Parse tanggal & bulan dari pesan natural (ID/EN)."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MONTH_ID: dict[str, int] = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "october": 10,
    "december": 12,
}

_ALL_TIME_PHRASES = ("semua bulan", "semua waktu", "sepanjang waktu", "all time")
_CURRENT_MONTH_PHRASES = ("bulan ini", "bulan sekarang", "this month")
_LAST_MONTH_PHRASES = ("bulan lalu", "bulan kemarin", "last month")

_MONTH_NAME_ALT = "|".join(re.escape(w) for w in sorted(MONTH_ID.keys(), key=len, reverse=True))


@dataclass
class MonthFilter:
    prefix: str | None  # YYYY-MM
    all_time: bool = False
    explicit: bool = False


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _prev_month_prefix(now: datetime | None = None) -> str:
    now = now or datetime.now()
    y, m = _shift_month(now.year, now.month, -1)
    return f"{y}-{m:02d}"


def month_filter_from_text(text: str) -> MonthFilter:
    """Baca filter bulan dari teks query."""
    lower = (text or "").lower()
    if any(p in lower for p in _ALL_TIME_PHRASES):
        return MonthFilter(prefix=None, all_time=True, explicit=True)
    if any(p in lower for p in _CURRENT_MONTH_PHRASES):
        return MonthFilter(prefix=datetime.now().strftime("%Y-%m"), explicit=True)
    if any(p in lower for p in _LAST_MONTH_PHRASES):
        return MonthFilter(prefix=_prev_month_prefix(), explicit=True)
    for word, num in MONTH_ID.items():
        if re.search(rf"\b{re.escape(word)}\b", lower):
            y = datetime.now().year
            return MonthFilter(prefix=f"{y}-{num:02d}", explicit=True)
    return MonthFilter(prefix=None, all_time=False, explicit=False)


def resolve_query_month(text: str) -> str | None:
    """Default bulan ini; None hanya jika user minta semua waktu."""
    mf = month_filter_from_text(text)
    if mf.all_time:
        return None
    if mf.prefix:
        return mf.prefix
    return datetime.now().strftime("%Y-%m")


def month_stop_words() -> frozenset[str]:
    return frozenset(MONTH_ID.keys()) | frozenset({"lalu", "kemarin", "tgl", "tanggal", "lusa"})


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    last = calendar.monthrange(year, month)[1]
    if day < 1 or day > last:
        return None
    return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)


def _parse_year(raw: str | None, now: datetime) -> int:
    if not raw:
        return now.year
    y = int(raw)
    if y < 100:
        y += 2000
    return y


def datetime_to_created_at(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def extract_expense_datetime(text: str) -> tuple[str | None, str]:
    """Ambil tanggal transaksi; kembalikan (created_at ISO atau None=sekarang, teks bersih)."""
    raw = (text or "").strip()
    if not raw:
        return None, raw

    now = datetime.now()
    lower = raw.lower()

    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"\bkemarin\b", re.I), "kemarin"),
        (re.compile(r"\byesterday\b", re.I), "yesterday"),
        (re.compile(r"\blusa\b", re.I), "lusa"),
        (
            re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_NAME_ALT})\b", re.I),
            "day_month",
        ),
        (
            re.compile(rf"\b({_MONTH_NAME_ALT})\s+(\d{{1,2}})\b", re.I),
            "month_day",
        ),
        (re.compile(r"\btgl\.?\s*(\d{1,2})\b", re.I), "tgl"),
        (
            re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b"),
            "slash",
        ),
    ]

    for pattern, kind in patterns:
        m = pattern.search(raw)
        if not m:
            continue

        dt: datetime | None = None
        if kind == "kemarin":
            dt = _safe_date(now.year, now.month, now.day) - timedelta(days=1)
        elif kind == "yesterday":
            dt = _safe_date(now.year, now.month, now.day) - timedelta(days=1)
        elif kind == "lusa":
            dt = _safe_date(now.year, now.month, now.day) - timedelta(days=2)
        elif kind == "day_month":
            day = int(m.group(1))
            month = MONTH_ID[m.group(2).lower()]
            dt = _safe_date(now.year, month, day)
        elif kind == "month_day":
            month = MONTH_ID[m.group(1).lower()]
            day = int(m.group(2))
            dt = _safe_date(now.year, month, day)
        elif kind == "tgl":
            day = int(m.group(1))
            dt = _safe_date(now.year, now.month, day)
        elif kind == "slash":
            day = int(m.group(1))
            month = int(m.group(2))
            year = _parse_year(m.group(3), now)
            dt = _safe_date(year, month, day)

        if dt is None:
            continue

        cleaned = (raw[: m.start()] + raw[m.end() :]).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        return datetime_to_created_at(dt), cleaned

    return None, raw
