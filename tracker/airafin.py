"""Sinkron ke airafin-dashboard (PostgreSQL + optional Google Sheets via backend)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from tracker import sheets
from tracker.env import load_env_local

logger = logging.getLogger(__name__)

_MONTH_EN = sheets._MONTH_EN  # noqa: SLF001 — shared month names with Sheets layout

_category_id_by_name: dict[str, int] | None = None
_env_loaded = False


def _ensure_env() -> None:
    global _env_loaded
    if not _env_loaded:
        load_env_local()
        _env_loaded = True


def is_enabled() -> bool:
    _ensure_env()
    return os.environ.get("AIRAFIN_API_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def config_error() -> str | None:
    _ensure_env()
    if not is_enabled():
        return "AIRAFIN_API_ENABLED=false"
    base = os.environ.get("AIRAFIN_API_URL", "").strip().rstrip("/")
    token = os.environ.get("API_SECRET_TOKEN", "").strip()
    if not base:
        return "AIRAFIN_API_URL kosong"
    if not token:
        return "API_SECRET_TOKEN kosong"
    # Backend API is :3081 — not nginx :3080 redirect or frontend :13080 (requires login).
    if ":3080" in base or ":13080" in base:
        return "AIRAFIN_API_URL harus backend :3081 (bukan frontend :3080/:13080)"
    if Path("/.dockerenv").is_file() and ("127.0.0.1" in base or "localhost" in base):
        return "Di Docker, AIRAFIN_API_URL=http://host.docker.internal:3081 (bukan 127.0.0.1)"
    return None


def _api_base() -> str:
    return os.environ.get("AIRAFIN_API_URL", "").strip().rstrip("/")


def _api_token() -> str:
    return os.environ.get("API_SECRET_TOKEN", "").strip()


def _request(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    err = config_error()
    if err:
        raise RuntimeError(err)

    url = f"{_api_base()}{path}"
    data = None
    headers: dict[str, str] = {"X-API-Token": _api_token()}
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
        try:
            payload = json.loads(detail)
            message = payload.get("error") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise RuntimeError(f"Airafin API {exc.code}: {message}") from exc


def _parse_created_at(created_at: str) -> datetime:
    return datetime.fromisoformat(created_at.strip().replace("Z", "+00:00"))


def period_from_created_at(created_at: str) -> str:
    """2026-06-11T… → 'June 2026' (format dashboard)."""
    dt = _parse_created_at(created_at)
    month = _MONTH_EN[dt.month] if 1 <= dt.month <= 12 else _MONTH_EN[datetime.now().month]
    return f"{month} {dt.year}"


def period_from_month(month: str | None = None) -> str:
    """YYYY-MM / JUNE / mei / None → 'June 2026'."""
    if not month or not str(month).strip():
        now = datetime.now()
        return f"{_MONTH_EN[now.month]} {now.year}"

    m = str(month).strip()
    if len(m) == 7 and "-" in m:
        try:
            dt = datetime.strptime(f"{m}-01", "%Y-%m-%d")
            return f"{_MONTH_EN[dt.month]} {dt.year}"
        except ValueError:
            pass

    from tracker.dates import MONTH_ID, month_prefix_to_budget_sheet
    from tracker.dates import _MONTH_EN as BUDGET_TABS  # noqa: SLF001

    lower = m.lower()
    if lower in MONTH_ID:
        return f"{_MONTH_EN[MONTH_ID[lower]]} {datetime.now().year}"

    tab = month_prefix_to_budget_sheet(m)
    if tab in BUDGET_TABS:
        month_num = BUDGET_TABS.index(tab) + 1
        return f"{_MONTH_EN[month_num]} {datetime.now().year}"

    now = datetime.now()
    return f"{_MONTH_EN[now.month]} {now.year}"


def normalize_pic(attributed_to: str | None) -> str:
    default = os.environ.get("FINTRACKER_DEFAULT_PIC", "Derwin").strip() or "Derwin"
    if default not in ("Derwin", "Anggita"):
        default = "Derwin"

    raw = (attributed_to or "").strip().lower()
    if raw in ("a", "anggita") or "anggita" in raw:
        return "Anggita"
    if raw in ("d", "derwin") or "derwin" in raw:
        return "Derwin"
    return default


def _load_categories() -> dict[str, int]:
    global _category_id_by_name
    if _category_id_by_name is not None:
        return _category_id_by_name

    payload = _request("GET", "/api/categories")
    mapping: dict[str, int] = {}
    for cat in payload.get("categories", []):
        name = str(cat.get("name", "")).strip()
        cid = cat.get("id")
        if name and isinstance(cid, int):
            mapping[name] = cid
    _category_id_by_name = mapping
    return mapping


def resolve_category_id(expense: dict[str, Any]) -> int:
    name = sheets._sheet_category(expense)  # noqa: SLF001
    mapping = _load_categories()
    if name in mapping:
        return mapping[name]
    raise RuntimeError(f"Kategori '{name}' tidak ada di dashboard")


def expense_to_body(expense: dict[str, Any]) -> dict[str, Any]:
    created_at = str(expense.get("created_at") or "")
    amount = int(expense.get("amount") or 0)
    if amount <= 0:
        raise RuntimeError("Nominal harus positif untuk sinkron dashboard")

    return {
        "date": sheets._sheet_date(created_at),  # noqa: SLF001
        "categoryId": resolve_category_id(expense),
        "detail": (expense.get("note") or "").strip() or "—",
        "cost": amount,
        "period": period_from_created_at(created_at),
        "pic": normalize_pic(expense.get("attributed_to")),
        "status": os.environ.get("AIRAFIN_DEFAULT_STATUS", "Done").strip() or "Done",
    }


def sync_append(expense: dict[str, Any], conn: Any | None = None) -> int | None:
    """POST transaksi ke dashboard. Kembalikan backend id atau None."""
    if not is_enabled():
        return None
    try:
        body = expense_to_body(expense)
        result = _request("POST", "/api/transactions", body)
        tx = result.get("transaction") or {}
        backend_id = tx.get("id")
        if backend_id is None:
            raise RuntimeError("Dashboard tidak mengembalikan transaction.id")

        sheets_sync = result.get("sheetsSync") or {}
        if sheets_sync.get("status") == "failed":
            logger.warning(
                "Airafin: DB tersimpan #%s, Sheets gagal: %s",
                backend_id,
                sheets_sync.get("error"),
            )

        if conn is not None and expense.get("id") is not None:
            from tracker.db import set_backend_id

            set_backend_id(conn, expense_id=int(expense["id"]), backend_id=int(backend_id))

        return int(backend_id)
    except Exception as exc:
        logger.warning("Airafin append gagal: %s", exc)
        return None


def sync_delete(backend_id: int) -> None:
    if not is_enabled() or not backend_id:
        return
    try:
        err = config_error()
        if err:
            raise RuntimeError(err)
        url = f"{_api_base()}/api/transactions/{int(backend_id)}"
        req = urllib.request.Request(
            url,
            method="DELETE",
            headers={"X-API-Token": _api_token()},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"DELETE gagal ({resp.status})")
    except Exception as exc:
        logger.warning("Airafin delete #%s gagal: %s", backend_id, exc)


def _fetch_summary(month: str | None = None) -> dict[str, Any]:
    period = urllib.parse.quote(period_from_month(month))
    return _request("GET", f"/api/dashboard/summary?period={period}")


def read_category_balance(category: str, month: str | None = None) -> dict[str, Any]:
    label = sheets.resolve_budget_category(category)
    if not label:
        return {"ok": False, "error": "unknown_category", "category": category}

    try:
        summary = _fetch_summary(month)
        period = summary.get("period") or period_from_month(month)
        for item in summary.get("categories", []):
            if item.get("categoryName") == label:
                plan = int(item.get("allocated") or 0)
                spent = int(item.get("spent") or 0)
                remaining = int(item.get("sisa") or 0)
                return {
                    "ok": True,
                    "month_sheet": period,
                    "category": label,
                    "plan": plan,
                    "spent": spent,
                    "remaining": remaining,
                    "is_total": False,
                }
        return {
            "ok": False,
            "error": "not_found",
            "category": label,
            "month_sheet": period,
        }
    except Exception as exc:
        logger.warning("Airafin sisa gagal: %s", exc)
        return {"ok": False, "error": "api_error", "detail": str(exc)}


def read_all_balances(month: str | None = None) -> dict[str, Any]:
    try:
        summary = _fetch_summary(month)
        period = summary.get("period") or period_from_month(month)
        categories = []
        for item in summary.get("categories", []):
            plan = int(item.get("allocated") or 0)
            spent = int(item.get("spent") or 0)
            remaining = int(item.get("sisa") or 0)
            if plan == 0 and spent == 0:
                continue
            categories.append(
                {
                    "category": item.get("categoryName"),
                    "plan": plan,
                    "spent": spent,
                    "remaining": remaining,
                    "is_total": False,
                }
            )
        if not categories:
            return {"ok": False, "error": "empty", "month_sheet": period}

        total_plan = int(summary.get("totalBudgetAllocated") or 0)
        total_spent = int(summary.get("totalSpent") or 0)
        total_remaining = int(summary.get("totalSisa") or 0)
        grand = {
            "category": "Grand Total",
            "plan": total_plan,
            "spent": total_spent,
            "remaining": total_remaining,
            "is_total": True,
        }
        return {
            "ok": True,
            "month_sheet": period,
            "categories": categories,
            "grand_total": grand,
        }
    except Exception as exc:
        logger.warning("Airafin sisa semua gagal: %s", exc)
        return {"ok": False, "error": "api_error", "detail": str(exc)}


def low_balance_warning(expense: dict[str, Any]) -> str:
    if not is_enabled():
        return ""
    if int(expense.get("amount") or 0) <= 0:
        return ""
    try:
        pct_limit = float(os.environ.get("FINTRACKER_SISA_WARN_PCT", "0.1"))
    except ValueError:
        pct_limit = 0.1

    sheet_cat = sheets._sheet_category(expense)  # noqa: SLF001
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
