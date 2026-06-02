"""Sinkron opsional ke Google Sheets (service account, Sheets API v4)."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

# Layout bawaan (8 kolom) vs "detail" (Mahardiora: Date, Category, Detail, Cost, Periode + id di F)
_DEFAULT_HEADERS = [
    "id",
    "created_at",
    "user_id",
    "amount",
    "currency",
    "category",
    "note",
    "source",
]

# Kategori valid di sheet DETAIL (Mahardiora)
_SHEET_CATEGORIES = frozenset(
    {
        "Emergency",
        "Entertain",
        "Family",
        "Maintenance",
        "Personal Savings",
        "Primary",
        "Savings",
        "Daily",
        "Transport",
    }
)

# Kategori internal bot (parse.py) → sheet
_BOT_TO_SHEET: dict[str, str] = {
    "makan": "Daily",
    "minuman": "Daily",
    "belanja": "Daily",
    "transport": "Transport",
    "tagihan": "Primary",
    "maintenance": "Maintenance",
    "savings": "Savings",
    "hiburan": "Entertain",
    "kesehatan": "Primary",
    "lainnya": "Daily",
}

# Kata kunci di catatan (urutan: lebih spesifik dulu)
_NOTE_TO_SHEET: tuple[tuple[tuple[str, ...], str], ...] = (
    (("darurat", "emergency", "ugd", "igd"), "Emergency"),
    (("netflix", "nonton", "bioskop", "game", "hiburan", "entertain"), "Entertain"),
    (("keluarga", "anak", "family", "ortu", "orang tua"), "Family"),
    (("reksadana", "reksa dana", "emas", "antam", "saham", "deposito", "tabungan", "invest"), "Savings"),
    (("personal saving", "tabungan pribadi"), "Personal Savings"),
    (
        (
            "listrik",
            "pln",
            "pdam",
            "tagihan air",
            "wifi",
            "internet",
            "infaq",
            "infak",
            "zakat",
            "sedekah",
            "donasi",
            "ipl",
            "kur mobil",
            "kredit mobil",
            "angsuran mobil",
            "cicilan rumah",
        ),
        "Primary",
    ),
    (
        (
            "cuci ac",
            "servis ac",
            "perbaiki ac",
            "bengkel",
            "keran",
            "kabel",
            "tukang",
            "perbaikan",
            "maintenance",
            "service ac",
        ),
        "Maintenance",
    ),
    (("gojek", "grab", "ojek", "bensin", "parkir", "tol", "taxi", "kereta", "bus"), "Transport"),
    (
        ("belanja", "indomaret", "alfamart", "supermarket", "hypermart", "makanan", "makan", "snack"),
        "Daily",
    ),
    (("kopi", "coffee", "teh", "sarapan", "lunch", "dinner"), "Daily"),
)

_MONTH_EN = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def is_enabled() -> bool:
    return os.environ.get("GOOGLE_SHEETS_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _layout() -> str:
    return os.environ.get("GOOGLE_SHEETS_LAYOUT", "default").strip().lower()


def sheets_config_error() -> str | None:
    """Penyebab sheets_config; None jika OK."""
    if not is_enabled():
        return "GOOGLE_SHEETS_ENABLED=false"
    sheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not sheet_id:
        return "GOOGLE_SHEETS_SPREADSHEET_ID kosong"
    if not creds:
        return "GOOGLE_SERVICE_ACCOUNT_FILE kosong"
    path = Path(creds).expanduser()
    if not path.is_absolute():
        repo = Path(__file__).resolve().parent.parent
        path = (repo / path).resolve()
    if not path.is_file():
        return f"file kredensial tidak ada: {path}"
    return None


def _config() -> tuple[str, Path, str] | None:
    err = sheets_config_error()
    if err:
        logger.warning("Google Sheets: %s", err)
        return None
    sheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    worksheet = os.environ.get("GOOGLE_SHEETS_WORKSHEET", "Pengeluaran").strip() or "Pengeluaran"
    path = Path(creds).expanduser()
    if not path.is_absolute():
        path = (Path(__file__).resolve().parent.parent / path).resolve()
    return sheet_id, path, worksheet


def _credentials(creds_path: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(str(creds_path), scopes=_SCOPES)
    creds.refresh(Request())
    return creds


def _request(method: str, url: str, creds, body: dict | None = None) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {creds.token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Sheets API {exc.code}: {detail}") from exc


def _parse_created_at(created_at: str) -> datetime:
    s = created_at.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _sheet_date(created_at: str) -> str:
    dt = _parse_created_at(created_at)
    return dt.strftime("%Y-%m-%d")


def _sheet_periode(created_at: str) -> str:
    from tracker.dates import budget_sheet_from_created_at, month_num_to_budget_sheet

    return budget_sheet_from_created_at(created_at) or month_num_to_budget_sheet(datetime.now().month)


# Hint kata → kategori sheet (urut panjang dulu agar "personal savings" sebelum "savings")
_CATEGORY_PARSE_HINTS: tuple[tuple[str, str], ...] = (
    ("personal savings", "Personal Savings"),
    ("entertainment", "Entertain"),
    ("entertain", "Entertain"),
    ("maintenance", "Maintenance"),
    ("emergency", "Emergency"),
    ("transport", "Transport"),
    ("savings", "Savings"),
    ("family", "Family"),
    ("primary", "Primary"),
    ("daily", "Daily"),
)


def find_explicit_sheet_category(text: str) -> tuple[str | None, str]:
    """
    Ambil kategori Mahardiora dari pesan jika disebut eksplisit.
    Contoh: 'Entertain jus 10k' → Entertain; 'jus 10k daily' → Daily.
    Jika beberapa kategori, yang paling akhir di teks yang dipakai.
    """
    raw = (text or "").strip()
    if not raw:
        return None, raw
    lower = raw.lower()
    hits: list[tuple[int, int, str]] = []
    for hint, label in _CATEGORY_PARSE_HINTS:
        for m in re.finditer(rf"\b{re.escape(hint)}\b", lower):
            hits.append((m.start(), m.end(), label))
    if not hits:
        return None, raw
    hits.sort(key=lambda x: x[0])
    start, end, label = hits[-1]
    stripped = (raw[:start] + raw[end:]).strip()
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,.-")
    return label, stripped or raw


def resolve_budget_category(name: str) -> str | None:
    """Map 'daily' / 'Daily' / 'personal savings' → nama kategori di sheet MAY/JUNE."""
    raw = (name or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    for cat in sorted(_SHEET_CATEGORIES, key=len, reverse=True):
        if cat.lower() == lower:
            return cat
    compact = lower.replace(" ", "")
    for cat in _SHEET_CATEGORIES:
        if cat.lower().replace(" ", "") == compact:
            return cat
    aliases = {
        "daily": "Daily",
        "transport": "Transport",
        "primary": "Primary",
        "saving": "Savings",
        "savings": "Savings",
        "emergency": "Emergency",
        "entertain": "Entertain",
        "entertainment": "Entertain",
        "entertaint": "Entertain",
        "family": "Family",
        "maintenance": "Maintenance",
        "personalsavings": "Personal Savings",
    }
    if compact in aliases:
        return aliases[compact]
    for key, label in aliases.items():
        if key in lower:
            return label
    return None


def category_from_query(text: str) -> str | None:
    """Contoh: 'sisa daily bulan ini' → Daily."""
    lower = (text or "").lower()
    if not any(k in lower for k in ("sisa", "saldo", "remaining", "anggaran")):
        return None
    from tracker.dates import strip_month_words

    cleaned = strip_month_words(text)
    if cleaned:
        cat = resolve_budget_category(cleaned)
        if cat:
            return cat
    return resolve_budget_category(text)


def month_to_budget_sheet(month: str | None = None) -> str:
    """Bulan ini → JUNE; atau terima JUNE / 2026-06 / mei."""
    from tracker.dates import month_prefix_to_budget_sheet

    return month_prefix_to_budget_sheet(month)


def _parse_sheet_amount(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    s = str(value).replace(",", "").strip()
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def _budget_range(worksheet: str) -> str:
    custom = os.environ.get("GOOGLE_SHEETS_BUDGET_RANGE", "").strip()
    if custom:
        return f"'{worksheet}'!{custom}"
    return f"'{worksheet}'!A2:E25"


def _parse_budget_row(row: list) -> dict[str, Any] | None:
    if not row:
        return None
    name_cell = (row[0] if len(row) > 0 else "").strip()
    if not name_cell or name_cell.lower() == "category":
        return None
    if name_cell.lower() == "grand total":
        plan = _parse_sheet_amount(row[1] if len(row) > 1 else 0)
        spent = _parse_sheet_amount(row[3] if len(row) > 3 else 0)
        remaining = _parse_sheet_amount(row[4] if len(row) > 4 else 0)
        if remaining == 0 and plan and spent:
            remaining = plan - spent
        return {
            "category": "Grand Total",
            "plan": plan,
            "spent": spent,
            "remaining": remaining,
            "is_total": True,
        }
    label = resolve_budget_category(name_cell)
    if not label:
        return None
    plan = _parse_sheet_amount(row[1] if len(row) > 1 else 0)
    spent = _parse_sheet_amount(row[3] if len(row) > 3 else 0)
    remaining = _parse_sheet_amount(row[4] if len(row) > 4 else 0)
    if remaining == 0 and plan and spent:
        remaining = plan - spent
    return {
        "category": label,
        "plan": plan,
        "spent": spent,
        "remaining": remaining,
        "is_total": False,
    }


def _fetch_budget_rows(month: str | None = None) -> tuple[str, list[dict[str, Any]]] | dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "error": "sheets_disabled"}
    cfg = _config()
    if not cfg:
        detail = sheets_config_error() or "sheets_config"
        return {"ok": False, "error": "sheets_config", "detail": detail}
    spreadsheet_id, creds_path, _detail_ws = cfg
    month_sheet = month_to_budget_sheet(month)
    creds = _credentials(creds_path)
    rng = urllib.parse.quote(_budget_range(month_sheet))
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng}"
    rows = _request("GET", url, creds).get("values", [])

    parsed: list[dict[str, Any]] = []
    for row in rows:
        item = _parse_budget_row(row)
        if item:
            parsed.append(item)
    return month_sheet, parsed


def read_category_balance(category: str, month: str | None = None) -> dict[str, Any]:
    """Baca satu kategori di sheet bulan (MAY, JUNE, …)."""
    label = resolve_budget_category(category)
    if not label:
        return {"ok": False, "error": "unknown_category", "category": category}

    fetched = _fetch_budget_rows(month)
    if isinstance(fetched, dict):
        return fetched
    month_sheet, parsed = fetched
    for item in parsed:
        if not item.get("is_total") and item["category"] == label:
            return {"ok": True, "month_sheet": month_sheet, **item}

    return {
        "ok": False,
        "error": "not_found",
        "category": label,
        "month_sheet": month_sheet,
    }


def read_all_balances(month: str | None = None) -> dict[str, Any]:
    """Semua kategori + Grand Total dari sheet bulan."""
    fetched = _fetch_budget_rows(month)
    if isinstance(fetched, dict):
        return fetched
    month_sheet, parsed = fetched
    categories = []
    seen: set[str] = set()
    for r in parsed:
        if r.get("is_total"):
            continue
        if r["category"] in seen:
            continue
        seen.add(r["category"])
        categories.append(r)
    grand = next((r for r in parsed if r.get("is_total")), None)
    if not categories:
        return {"ok": False, "error": "empty", "month_sheet": month_sheet}
    return {
        "ok": True,
        "month_sheet": month_sheet,
        "categories": categories,
        "grand_total": grand,
    }


def low_balance_warning(expense: dict[str, Any]) -> str:
    """Peringatan jika sisa kategori sheet < ambang (default 10% PLAN)."""
    if not is_enabled():
        return ""
    if int(expense.get("amount") or 0) <= 0:
        return ""
    try:
        pct_limit = float(os.environ.get("FINTRACKER_SISA_WARN_PCT", "0.1"))
    except ValueError:
        pct_limit = 0.1
    sheet_cat = _sheet_category(expense)
    from tracker.dates import budget_sheet_from_created_at

    month = budget_sheet_from_created_at(str(expense.get("created_at") or ""))
    bal = read_category_balance(sheet_cat, month)
    if not bal.get("ok"):
        return ""
    plan = int(bal.get("plan") or 0)
    remaining = int(bal.get("remaining") or 0)
    if plan <= 0:
        return ""
    if remaining <= 0 or remaining / plan <= pct_limit:
        from tracker.format import format_idr

        pct = int(round(100 * remaining / plan))
        return f"\n\n⚠️ Sisa {sheet_cat} tinggal {format_idr(remaining)} ({pct}% dari PLAN)"
    return ""


def _sheet_category(expense: dict[str, Any]) -> str:
    default = os.environ.get("GOOGLE_SHEETS_CATEGORY_DEFAULT", "Daily").strip() or "Daily"
    if default not in _SHEET_CATEGORIES:
        default = "Daily"

    explicit = resolve_budget_category(str(expense.get("category") or ""))
    if explicit:
        return explicit

    note = (expense.get("note") or "").lower()
    for keywords, label in _NOTE_TO_SHEET:
        if any(kw in note for kw in keywords):
            return label

    raw = (expense.get("category") or "").strip().lower()
    if raw in _BOT_TO_SHEET:
        return _BOT_TO_SHEET[raw]

    return default


def _sheet_id_cell(expense_id: Any) -> str:
    """Prefix # agar Google Sheets tidak mengubah 10 → tanggal 1900-01-10."""
    if expense_id is None:
        return ""
    return f"#{int(expense_id)}"


def _id_matches(cell: str, expense_id: int) -> bool:
    s = str(cell).strip()
    if not s:
        return False
    if s == str(expense_id) or s == f"#{expense_id}":
        return True
    if s.startswith("#") and s[1:].isdigit():
        return int(s[1:]) == expense_id
    return False


def _row_values(expense: dict[str, Any]) -> list[Any]:
    if _layout() == "detail":
        return [
            _sheet_date(str(expense.get("created_at", ""))),
            _sheet_category(expense),
            expense.get("note") or "",
            expense.get("amount"),
            _sheet_periode(str(expense.get("created_at", ""))),
            _sheet_id_cell(expense.get("id")),
            expense.get("attributed_to") or "",
        ]
    return [
        expense.get("id"),
        expense.get("created_at"),
        expense.get("user_id"),
        expense.get("amount"),
        expense.get("currency"),
        expense.get("category") or "lainnya",
        expense.get("note"),
        expense.get("source"),
    ]


def _append_range(worksheet: str) -> str:
    if _layout() == "detail":
        return f"'{worksheet}'!A:G"
    return f"'{worksheet}'!A:H"


def _id_column() -> str:
    return "F" if _layout() == "detail" else "A"


def _sheet_gid(spreadsheet_id: str, worksheet: str, creds) -> int:
    meta = _request(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}?fields=sheets.properties",
        creds,
    )
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == worksheet:
            return int(props["sheetId"])
    if _layout() == "detail":
        raise RuntimeError(f"Worksheet '{worksheet}' tidak ditemukan — buat tab manual di spreadsheet.")
    body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": worksheet,
                        "gridProperties": {"rowCount": 1000, "columnCount": len(_DEFAULT_HEADERS)},
                    }
                }
            }
        ]
    }
    res = _request(
        "POST",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
        creds,
        body,
    )
    return int(res["replies"][0]["addSheet"]["properties"]["sheetId"])


def _ensure_headers(spreadsheet_id: str, worksheet: str, creds) -> None:
    if _layout() == "detail":
        return
    rng = urllib.parse.quote(f"'{worksheet}'!A1:H1")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng}"
    current = _request("GET", url, creds).get("values", [])
    if current and current[0]:
        return
    append_rng = urllib.parse.quote(f"'{worksheet}'!A1")
    _request(
        "POST",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{append_rng}:append"
        "?valueInputOption=USER_ENTERED",
        creds,
        {"values": [_DEFAULT_HEADERS]},
    )


def _find_row_index(spreadsheet_id: str, worksheet: str, expense_id: int, creds) -> int | None:
    col = _id_column()
    rng = urllib.parse.quote(f"'{worksheet}'!{col}:{col}")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng}"
    values = _request("GET", url, creds).get("values", [])
    for idx, row in enumerate(values, start=1):
        if row and _id_matches(str(row[0]), expense_id):
            return idx
    return None


def sync_append(expense: dict[str, Any]) -> None:
    if not is_enabled():
        return
    try:
        cfg = _config()
        if not cfg:
            return
        spreadsheet_id, creds_path, worksheet = cfg
        creds = _credentials(creds_path)
        eid = expense.get("id")
        if eid is not None and _find_row_index(spreadsheet_id, worksheet, int(eid), creds):
            logger.info("Google Sheets: id #%s sudah ada, skip append", eid)
            return
        _ensure_headers(spreadsheet_id, worksheet, creds)
        rng = urllib.parse.quote(_append_range(worksheet))
        _request(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{rng}:append"
            "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
            creds,
            {"values": [_row_values(expense)]},
        )
    except Exception as exc:
        logger.warning("Google Sheets append gagal: %s", exc)


def sync_delete(expense_id: int) -> None:
    if not is_enabled():
        return
    try:
        cfg = _config()
        if not cfg:
            return
        spreadsheet_id, creds_path, worksheet = cfg
        creds = _credentials(creds_path)
        row_idx = _find_row_index(spreadsheet_id, worksheet, expense_id, creds)
        if not row_idx:
            return
        gid = _sheet_gid(spreadsheet_id, worksheet, creds)
        _request(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            creds,
            {
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": gid,
                                "dimension": "ROWS",
                                "startIndex": row_idx - 1,
                                "endIndex": row_idx,
                            }
                        }
                    }
                ]
            },
        )
    except Exception as exc:
        logger.warning("Google Sheets delete gagal (id=%s): %s", expense_id, exc)
