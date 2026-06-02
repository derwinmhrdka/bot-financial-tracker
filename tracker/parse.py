"""Parse natural-language expense messages (Indonesian-friendly)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedExpense:
    amount: int
    note: str
    category: str | None
    attributed_to: str | None = None
    created_at: str | None = None


# Akhiran "- Anggita", "-A", "- D" → kolom nama di sheet (G), apa adanya
# Jangan dianggap nama orang (kategori sheet)
_NOT_PERSON_TOKENS = frozenset(
    {
        "daily",
        "transport",
        "primary",
        "savings",
        "entertain",
        "entertainment",
        "maintenance",
        "emergency",
        "family",
    }
)

_ATTRIBUTION_RE = re.compile(r"\s-\s*([A-Za-z][A-Za-z0-9\s]{0,24})\s*$")


_AMOUNT_PATTERNS = [
    # Rp 35.000 / Rp35000
    re.compile(
        r"(?:rp\.?\s*)?([\d][\d.,]*)\s*(?:rb|ribu|k|jt|juta|m|milyar)?",
        re.IGNORECASE,
    ),
    # standalone 35rb / 1.5jt
    re.compile(
        r"\b([\d][\d.,]*)\s*(rb|ribu|k|jt|juta|m|milyar)\b",
        re.IGNORECASE,
    ),
]

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "makan": ["makan", "makanan", "food", "lunch", "dinner", "sarapan", "snack"],
    "minuman": ["kopi", "coffee", "teh", "jus", "minuman"],
    "transport": ["gojek", "grab", "ojek", "bensin", "parkir", "tol", "transport", "taxi"],
    "belanja": ["belanja", "shopping", "supermarket", "indomaret", "alfamart", "hypermart"],
    "tagihan": [
        "listrik",
        "pln",
        "pdam",
        "air",
        "wifi",
        "internet",
        "pulsa",
        "tagihan",
        "bill",
        "infaq",
        "infak",
        "zakat",
        "sedekah",
        "donasi",
        "ipl",
        "kur mobil",
        "kredit mobil",
        "angsuran mobil",
    ],
    "maintenance": [
        "bengkel",
        "keran",
        "kabel",
        "cuci ac",
        "servis ac",
        "perbaiki ac",
        "tukang",
        "perbaikan",
        "maintenance",
    ],
    "savings": ["tabungan", "reksadana", "reksa dana", "emas", "antam", "saham", "deposito", "invest"],
    "hiburan": ["nonton", "bioskop", "game", "hiburan", "netflix"],
    "kesehatan": ["obat", "dokter", "rumah sakit", "apotek", "kesehatan"],
}


def _normalize_number(raw: str) -> float:
    s = raw.strip().replace(" ", "")
    if "," in s and "." in s:
        # 1.234,56 → European; 1,234.56 → US — prefer last separator as decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 3 and len(parts) > 1:
            s = "".join(parts)
        else:
            s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def _apply_multiplier(value: float, suffix: str | None) -> int:
    if not suffix:
        return int(round(value))
    s = suffix.lower()
    if s in ("rb", "ribu", "k"):
        return int(round(value * 1_000))
    if s in ("jt", "juta"):
        return int(round(value * 1_000_000))
    if s in ("m", "milyar"):
        return int(round(value * 1_000_000_000))
    return int(round(value))


def extract_amount(text: str) -> tuple[int, str] | None:
    """Return (amount, remainder_text) or None."""
    for pattern in _AMOUNT_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        num_str = m.group(1)
        suffix = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        if not suffix and m.group(0).lower():
            tail = m.group(0).lower()
            for suf in ("ribu", "rb", "juta", "jt", "milyar", "m"):
                if suf in tail:
                    suffix = suf
                    break
            if "k" in tail and "rb" not in tail and "ribu" not in tail:
                suffix = "k"
        try:
            base = _normalize_number(num_str)
            amount = _apply_multiplier(base, suffix)
        except ValueError:
            continue
        if amount <= 0:
            continue
        remainder = (text[: m.start()] + text[m.end() :]).strip()
        remainder = re.sub(r"\s+", " ", remainder).strip(" ,.-")
        return amount, remainder
    return None


def resolve_person_label(token: str) -> str | None:
    """Simpan teks setelah '-' apa adanya (A, Anggita, D, …)."""
    raw = (token or "").strip()
    if not raw:
        return None
    if raw.lower() in _NOT_PERSON_TOKENS:
        return None
    if len(raw) > 24 or not raw.replace(" ", "").isalnum():
        return None
    return raw


def extract_attribution(text: str) -> tuple[str | None, str]:
    """Contoh: 'jus 10k -A' → ('A', 'jus 10k')."""
    raw = (text or "").strip()
    m = _ATTRIBUTION_RE.search(raw)
    if not m:
        return None, raw
    label = resolve_person_label(m.group(1))
    if not label:
        return None, raw
    stripped = raw[: m.start()].strip()
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,.-")
    return label, stripped or raw


def guess_category(text: str) -> str | None:
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


def parse_message(text: str) -> ParsedExpense | None:
    """Parse e.g. 'makan siang 35rb', 'makan 35rb kemarin', 'infaq 50k 15 mei'."""
    cleaned = text.strip()
    if not cleaned:
        return None

    from tracker.dates import extract_expense_datetime

    created_at, cleaned = extract_expense_datetime(cleaned)
    if not cleaned:
        return None

    extracted = extract_amount(cleaned)
    if not extracted:
        return None

    amount, remainder = extracted
    attributed_to, body = extract_attribution(remainder or cleaned)
    from tracker.sheets import find_explicit_sheet_category

    sheet_cat, _ = find_explicit_sheet_category(body)
    if not sheet_cat:
        sheet_cat, _ = find_explicit_sheet_category(cleaned)
    if sheet_cat:
        _, note = find_explicit_sheet_category(body)
        note = note or body
        category = sheet_cat
    else:
        note = body
        category = guess_category(note or body)
    return ParsedExpense(
        amount=amount,
        note=note,
        category=category,
        attributed_to=attributed_to,
        created_at=created_at,
    )
