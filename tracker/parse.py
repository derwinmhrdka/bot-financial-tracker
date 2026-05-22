"""Parse natural-language expense messages (Indonesian-friendly)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedExpense:
    amount: int
    note: str
    category: str | None


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


def guess_category(text: str) -> str | None:
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


def parse_message(text: str) -> ParsedExpense | None:
    """Parse e.g. 'makan siang 35rb' or 'gojek 15k ke kantor'."""
    cleaned = text.strip()
    if not cleaned:
        return None

    extracted = extract_amount(cleaned)
    if not extracted:
        return None

    amount, remainder = extracted
    note = remainder or cleaned
    category = guess_category(cleaned)
    return ParsedExpense(amount=amount, note=note, category=category)
