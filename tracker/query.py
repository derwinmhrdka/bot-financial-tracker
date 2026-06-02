"""Parse & jalankan pertanyaan riwayat pengeluaran."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tracker.dates import month_filter_from_text, month_stop_words, resolve_query_month
from tracker.parse import extract_amount

_QUERY_MARKERS = (
    "berapa",
    "sudah",
    "kali",
    "tampilkan",
    "tunjukkan",
    "cari",
    "yang ",
    "riwayat",
    "?",
)

_STOP_WORDS = frozenset(
    {
        "sudah",
        "berapa",
        "kali",
        "bulan",
        "ini",
        "sekarang",
        "yang",
        "di",
        "ke",
        "dari",
        "untuk",
        "dan",
        "atau",
        "ada",
        "saya",
        "aku",
        "kita",
        "the",
        "lebih",
        "kurang",
        "atas",
        "bawah",
        "dari",
        "semua",
        "saja",
        "berapa",
        "total",
        "jumlah",
        "nominal",
        "tanggal",
        "kapan",
        "lalu",
        "kemarin",
        "lusa",
        "tgl",
    }
) | month_stop_words()


def _extract_category(text: str) -> str | None:
    from tracker.sheets import resolve_budget_category

    lower = text.lower()
    for cat in (
        "Personal Savings",
        "Entertain",
        "Maintenance",
        "Emergency",
        "Transport",
        "Savings",
        "Primary",
        "Family",
        "Daily",
    ):
        if re.search(rf"\b{re.escape(cat.lower())}\b", lower):
            return resolve_budget_category(cat)
    return resolve_budget_category(text)


@dataclass
class ParsedQuery:
    keywords: list[str]
    category: str | None
    month_prefix: str | None  # YYYY-MM; None = semua waktu
    min_amount: int | None
    max_amount: int | None
    label: str  # judul untuk balasan


def _extract_thresholds(text: str) -> tuple[int | None, int | None]:
    lower = text.lower()
    min_a: int | None = None
    max_a: int | None = None

    for pattern, is_min in (
        (
            r"(?:lebih dari|di atas|minimal|min|>\s*)\s*([\d][\d.,\s]*(?:rb|ribu|k|jt|juta)?)",
            True,
        ),
        (
            r"(?:kurang dari|di bawah|maksimal|max|<\s*)\s*([\d][\d.,\s]*(?:rb|ribu|k|jt|juta)?)",
            False,
        ),
    ):
        m = re.search(pattern, lower)
        if not m:
            continue
        chunk = m.group(1).strip()
        if not re.search(r"\d", chunk):
            continue
        parsed = extract_amount(chunk) or extract_amount(f"{chunk} rb")
        if not parsed:
            continue
        amount = parsed[0]
        if is_min:
            min_a = amount
        else:
            max_a = amount
    return min_a, max_a


def _extract_keywords(text: str, category: str | None) -> list[str]:
    lower = text.lower()
    found: list[str] = []

    m = re.search(r"berapa\s+(?:kali\s+)?([a-z][a-z0-9]{1,20})", lower)
    if m:
        w = m.group(1)
        if w not in _STOP_WORDS and w != (category or "").lower():
            found.append(w)

    cleaned = lower
    for word in sorted(_STOP_WORDS, key=len, reverse=True):
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned)
    if category:
        cleaned = re.sub(rf"\b{re.escape(category.lower())}\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(?:lebih dari|kurang dari|di atas|di bawah|rb|ribu|jt|juta)\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"[\d.,]+", " ", cleaned)

    for token in cleaned.split():
        t = token.strip(".,?!:;\"'()[]")
        if len(t) < 2 or t in _STOP_WORDS:
            continue
        if t not in found:
            found.append(t)

    return found[:3]


def _build_label(keywords: list[str], category: str | None, month_prefix: str | None, min_a, max_a) -> str:
    parts: list[str] = []
    if category:
        parts.append(category)
    elif keywords:
        parts.append(keywords[0])
    else:
        parts.append("pencarian")
    if min_a is not None:
        from tracker.format import format_idr

        parts.append(f"> {format_idr(min_a)}")
    if max_a is not None:
        from tracker.format import format_idr

        parts.append(f"< {format_idr(max_a)}")
    if month_prefix:
        try:
            dt = datetime.strptime(month_prefix + "-01", "%Y-%m-%d")
            parts.append(dt.strftime("%b %Y"))
        except ValueError:
            parts.append(month_prefix)
    return " · ".join(parts)


def parse_query(text: str) -> ParsedQuery | None:
    raw = (text or "").strip()
    if not raw:
        return None

    lower = raw.lower()
    if re.search(r"\b(pindah|transfer)\b", lower):
        return None
    if any(k in lower for k in ("sisa", "saldo")) and "berapa" not in lower:
        return None
    if lower.startswith(("total", "ringkasan", "summary", "rekap")):
        return None
    if re.search(r"\bundo\b", lower) or re.search(r"\b(?:hapus|delete)\s+#?\d+", lower):
        return None

    has_marker = any(m in lower for m in _QUERY_MARKERS)
    min_a, max_a = _extract_thresholds(raw)
    has_threshold = min_a is not None or max_a is not None
    month_info = month_filter_from_text(raw)
    has_explicit_month = month_info.explicit
    category = _extract_category(raw)
    month_prefix = resolve_query_month(raw)
    keywords = _extract_keywords(raw, category)

    if not has_marker and not has_threshold and "?" not in raw and not has_explicit_month:
        return None
    if not keywords and not category and not has_threshold:
        return None

    # Hindari tertukar perintah catat: "makan 35rb" / "infaq 50k 15 mei"
    if extract_amount(raw) and not has_marker and not has_threshold:
        return None
    if not has_marker and not has_threshold and not has_explicit_month:
        return None

    label = _build_label(keywords, category, month_prefix, min_a, max_a)
    return ParsedQuery(
        keywords=keywords,
        category=category,
        month_prefix=month_prefix,
        min_amount=min_a,
        max_amount=max_a,
        label=label,
    )


def search_expenses(
    conn: Any,
    *,
    user_id: str,
    spec: ParsedQuery,
    limit: int = 40,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM expenses WHERE user_id = ?"
    params: list[Any] = [user_id]

    q += " AND (source IS NULL OR source != 'transfer')"

    if spec.month_prefix:
        q += " AND created_at LIKE ?"
        params.append(f"{spec.month_prefix}%")

    if spec.category:
        q += " AND LOWER(COALESCE(category, '')) LIKE ?"
        params.append(f"%{spec.category.lower()}%")

    if spec.keywords:
        kw_parts = []
        for kw in spec.keywords:
            p = f"%{kw.lower()}%"
            kw_parts.append("(LOWER(note) LIKE ? OR LOWER(COALESCE(category, '')) LIKE ?)")
            params.extend([p, p])
        q += " AND (" + " OR ".join(kw_parts) + ")"

    if spec.min_amount is not None:
        q += " AND amount >= ?"
        params.append(spec.min_amount)

    if spec.max_amount is not None:
        q += " AND amount <= ?"
        params.append(spec.max_amount)

    q += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]
