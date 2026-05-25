"""Parse perintah pindah saldo antar kategori."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tracker.parse import extract_amount


@dataclass
class ParsedTransfer:
    from_category: str
    to_category: str
    amount: int


def parse_transfer(text: str) -> ParsedTransfer | None:
    """
    Contoh: 'pindah daily to entertain 100k' → Daily +100k, Entertain -100k.
    """
    raw = (text or "").strip()
    if not re.search(r"\b(pindah|transfer)\b", raw, re.IGNORECASE):
        return None

    body = re.sub(
        r"^\s*(?:pindah|transfer)\s+(?:saldo\s+)?",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    if not body:
        return None

    extracted = extract_amount(body)
    if not extracted:
        return None
    amount, remainder = extracted
    if amount <= 0:
        return None

    m = re.search(r"^(.+?)\s+(?:to|ke)\s+(.+)$", remainder.strip(), re.IGNORECASE)
    if not m:
        return None

    from tracker.sheets import resolve_budget_category

    from_cat = resolve_budget_category(m.group(1).strip())
    to_cat = resolve_budget_category(m.group(2).strip())
    if not from_cat or not to_cat:
        return None
    if from_cat == to_cat:
        return None

    return ParsedTransfer(from_category=from_cat, to_category=to_cat, amount=amount)
