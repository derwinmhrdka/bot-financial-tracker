"""Parse tanggal & bulan dari pesan natural (ID/EN). Tab sheet: JANUARY … DECEMBER."""

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

_MONTH_EN = (
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
)

_ALL_TIME_PHRASES = ("semua bulan", "semua waktu", "sepanjang waktu", "all time")
_CURRENT_MONTH_PHRASES = ("bulan ini", "bulan sekarang", "this month")
_LAST_MONTH_PHRASES = ("bulan lalu", "bulan kemarin", "last month")

_MONTH_NAME_ALT = "|".join(re.escape(w) for w in sorted(MONTH_ID.keys(), key=len, reverse=True))


def month_num_to_budget_sheet(month: int) -> str:
    """Angka bulan 1–12 → nama tab (JUNE, AUGUST, …)."""
    if 1 <= month <= 12:
        return _MONTH_EN[month - 1]
    return _MONTH_EN[datetime.now().month - 1]


def month_prefix_to_budget_sheet(month: str | None = None) -> str:
    """YYYY-MM / JUNE / mei / None → nama tab sheet Inggris."""
    if not month or not str(month).strip():
        return month_num_to_budget_sheet(datetime.now().month)

    m = str(month).strip()
    if len(m) == 7 and "-" in m:
        try:
            dt = datetime.strptime(f"{m}-01", "%Y-%m-%d")
            return month_num_to_budget_sheet(dt.month)
        except ValueError:
            pass

    lower = m.lower()
    if lower in MONTH_ID:
        return month_num_to_budget_sheet(MONTH_ID[lower])

    upper = m.upper()
    if upper in _MONTH_EN:
        return upper

    return month_num_to_budget_sheet(datetime.now().month)


def budget_sheet_from_created_at(created_at: str | None) -> str | None:
    """Bulan transaksi dari created_at → tab sheet (sesuai tanggal tercatat)."""
    if not created_at:
        return None
    try:
        s = str(created_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return month_num_to_budget_sheet(dt.month)
    except ValueError:
        return None


def current_month_prefix() -> str:
    return datetime.now().strftime("%Y-%m")


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
    """Baca bulan dari teks (mei, juni, bulan lalu, …)."""
    lower = (text or "").lower()
    if any(p in lower for p in _ALL_TIME_PHRASES):
        return MonthFilter(prefix=None, all_time=True, explicit=True)
    if any(p in lower for p in _CURRENT_MONTH_PHRASES):
        return MonthFilter(prefix=current_month_prefix(), explicit=True)
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
    return current_month_prefix()


def month_stop_words() -> frozenset[str]:
    return frozenset(MONTH_ID.keys()) | frozenset({"lalu", "kemarin", "tgl", "tanggal", "lusa", "bulan"})


def strip_month_words(text: str) -> str:
    """Hapus kata bulan dari teks (untuk parse kategori di 'sisa daily juni')."""
    cleaned = (text or "").strip()
    for phrase in sorted(
        (
            *_ALL_TIME_PHRASES,
            *_CURRENT_MONTH_PHRASES,
            *_LAST_MONTH_PHRASES,
            "bulan",
            "sisa",
            "saldo",
            "remaining",
            "anggaran",
        ),
        key=len,
        reverse=True,
    ):
        cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned, flags=re.I)
    for word in sorted(MONTH_ID.keys(), key=len, reverse=True):
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    """Tanggal eksplisit di pesan (15 mei, april, kemarin); None = hari ini."""
    raw = (text or "").strip()
    if not raw:
        return None, raw

    now = datetime.now()

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
        if kind in ("kemarin", "yesterday"):
            base = _safe_date(now.year, now.month, now.day)
            dt = base - timedelta(days=1) if base else None
        elif kind == "lusa":
            base = _safe_date(now.year, now.month, now.day)
            dt = base - timedelta(days=2) if base else None
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

    # Satu kata bulan saja di akhir: "Jajan 10k April"
    m = re.search(rf"\b({_MONTH_NAME_ALT})\s*$", raw, re.I)
    if m:
        month = MONTH_ID[m.group(1).lower()]
        dt = _safe_date(now.year, month, 1)
        if dt:
            cleaned = raw[: m.start()].strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
            return datetime_to_created_at(dt), cleaned

    return None, raw
