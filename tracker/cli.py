"""Command-line interface for the expense tracker."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tracker.db import (
    add_expense,
    connect,
    delete_expense,
    get_expense_by_id,
    get_last_expense,
    list_expenses,
    summary_expenses,
)
from tracker import sheets
from tracker.format import (
    format_add,
    format_error,
    format_help,
    format_idr,
    format_list,
    format_delete,
    format_sisa,
    format_sisa_all,
    format_summary,
    format_undo,
    format_transfer,
    format_query_result,
)
from tracker.parse import parse_message
from tracker.transfer import parse_transfer
from tracker.query import parse_query, search_expenses

_COMMANDS = frozenset({"add", "list", "summary", "undo", "delete", "sisa", "transfer", "query", "help"})
_FLAG_TAKES_VALUE = frozenset(
    {"--user-id", "--amount", "--category", "--note", "--text", "--source", "--limit", "--month", "--db"}
)


def _default_user_id() -> str:
    import os

    raw = os.environ.get("FINTRACKER_DEFAULT_USER_ID", "").strip()
    if not raw:
        raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")[0].strip()
    if not raw:
        return ""
    return raw if raw.startswith("telegram:") else f"telegram:{raw}"


def _split_global_flags(argv: list[str]) -> tuple[list[str], list[str]]:
    global_flags: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--db" and i + 1 < len(argv):
            global_flags.extend(["--db", argv[i + 1]])
            i += 2
            continue
        rest = argv[i:]
        break
    return global_flags, rest


def _normalize_add_tail(tail: list[str]) -> list[str]:
    if "--text" in tail or "--amount" in tail:
        out = list(tail)
    else:
        flags: list[str] = []
        text_parts: list[str] = []
        i = 0
        while i < len(tail):
            tok = tail[i]
            if tok.startswith("--"):
                flags.append(tok)
                if tok in _FLAG_TAKES_VALUE and i + 1 < len(tail):
                    flags.append(tail[i + 1])
                    i += 2
                    continue
            else:
                text_parts.append(tok)
            i += 1
        out = flags
        if text_parts:
            out = ["--text", " ".join(text_parts)] + out

    if "--user-id" not in out:
        uid = _default_user_id()
        if uid:
            out = ["--user-id", uid] + out
    if "--source" not in out:
        out = out + ["--source", "telegram"]
    return out


def _normalize_argv(argv: list[str]) -> list[str]:
    """Hermes agent often omits 'add' or passes bare message text as the command."""
    global_flags, rest = _split_global_flags(argv)
    if not rest:
        return global_flags

    joined = " ".join(rest)
    if rest[0] not in _COMMANDS and parse_query(joined):
        uid = _default_user_id()
        if uid:
            return global_flags + ["query", "--user-id", uid, "--text", joined]
    if rest[0] not in _COMMANDS and re.search(r"\b(pindah|transfer)\b", joined, re.IGNORECASE):
        uid = _default_user_id()
        if uid:
            return global_flags + ["transfer", "--user-id", uid, "--text", joined]
    if rest[0] not in _COMMANDS and any(k in joined.lower() for k in ("sisa", "saldo")):
        uid = _default_user_id()
        if uid:
            return global_flags + ["sisa", "--user-id", uid, "--text", joined]

    if rest[0] not in _COMMANDS:
        text = " ".join(rest)
        uid = _default_user_id()
        if not uid:
            return global_flags + rest
        return global_flags + [
            "add",
            "--user-id",
            uid,
            "--text",
            text,
            "--source",
            "telegram",
        ]

    if rest[0] == "add":
        return global_flags + ["add"] + _normalize_add_tail(rest[1:])

    if rest[0] == "sisa":
        return global_flags + ["sisa"] + _normalize_sisa_tail(rest[1:])

    return argv


def _normalize_sisa_tail(tail: list[str]) -> list[str]:
    if "--category" in tail or "--text" in tail:
        out = list(tail)
    else:
        text_parts: list[str] = []
        flags: list[str] = []
        i = 0
        while i < len(tail):
            tok = tail[i]
            if tok.startswith("--"):
                flags.append(tok)
                if tok in _FLAG_TAKES_VALUE and i + 1 < len(tail):
                    flags.append(tail[i + 1])
                    i += 2
                    continue
            else:
                text_parts.append(tok)
            i += 1
        out = flags
        if text_parts:
            out = ["--text", " ".join(text_parts)] + out
    if "--user-id" not in out:
        uid = _default_user_id()
        if uid:
            out = ["--user-id", uid] + out
    return out


def _emit(payload: dict, code: int = 0) -> int:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    except (AttributeError, OSError):
        print(text)
    return code


def cmd_add(args: argparse.Namespace) -> int:
    amount, note, category = args.amount, args.note or "", args.category
    if args.text:
        parsed = parse_message(args.text)
        if not parsed:
            return _emit(
                {"ok": False, "error": "parse_failed", "telegram_reply": format_error("Nominal tidak dikenali")},
                1,
            )
        amount = amount or parsed.amount
        note = note or parsed.note
        category = category or parsed.category
        attributed_to = getattr(parsed, "attributed_to", None)
        created_at = getattr(parsed, "created_at", None)
    else:
        attributed_to = None
        created_at = None
    if amount is None:
        return _emit(
            {"ok": False, "error": "missing_amount", "telegram_reply": format_error("Jumlah wajib diisi")},
            1,
        )
    with connect(Path(args.db) if args.db else None) as conn:
        row = add_expense(
            conn,
            user_id=args.user_id,
            amount=int(amount),
            category=category,
            note=note,
            source=args.source,
            attributed_to=attributed_to,
            created_at=created_at,
        )
    sheets.sync_append(row)
    reply = format_add(row) + sheets.low_balance_warning(row)
    return _emit({"ok": True, "expense": row, "telegram_reply": reply})


def cmd_list(args: argparse.Namespace) -> int:
    with connect(Path(args.db) if args.db else None) as conn:
        rows = list_expenses(conn, user_id=args.user_id, limit=args.limit, month=args.month)
    return _emit({"ok": True, "expenses": rows, "telegram_reply": format_list(rows, month=args.month)})


def cmd_summary(args: argparse.Namespace) -> int:
    month = args.month or datetime.now(timezone.utc).strftime("%Y-%m")
    with connect(Path(args.db) if args.db else None) as conn:
        data = summary_expenses(conn, user_id=args.user_id, month=month)
    data["month"] = month
    data["formatted_total"] = format_idr(data["total"])
    return _emit({"ok": True, **data, "telegram_reply": format_summary(data)})


def cmd_undo(args: argparse.Namespace) -> int:
    with connect(Path(args.db) if args.db else None) as conn:
        last = get_last_expense(conn, user_id=args.user_id)
        if not last:
            return _emit({"ok": False, "error": "empty", "telegram_reply": format_undo(None)}, 1)
        ok = delete_expense(conn, expense_id=last["id"], user_id=args.user_id)
    if ok and last:
        sheets.sync_delete(int(last["id"]))
    return _emit({"ok": ok, "removed": last if ok else None, "telegram_reply": format_undo(last if ok else None)}, 0 if ok else 1)


def cmd_delete(args: argparse.Namespace) -> int:
    eid = int(args.id)
    with connect(Path(args.db) if args.db else None) as conn:
        row = get_expense_by_id(conn, expense_id=eid, user_id=args.user_id)
        if not row:
            return _emit(
                {
                    "ok": False,
                    "error": "not_found",
                    "telegram_reply": f"❌ Entri #{eid} tidak ditemukan.",
                },
                1,
            )
        ok = delete_expense(conn, expense_id=eid, user_id=args.user_id)
    if ok:
        sheets.sync_delete(eid)
    return _emit(
        {"ok": ok, "removed": row if ok else None, "telegram_reply": format_delete(row if ok else None, eid)},
        0 if ok else 1,
    )


def cmd_sisa(args: argparse.Namespace) -> int:
    from tracker.dates import month_filter_from_text

    text = (args.text or "").lower()
    mf = month_filter_from_text(args.text or "") if args.text else None
    month = args.month or (mf.prefix if mf and mf.prefix else None)

    if args.all or "semua" in text or "all" in text:
        data = sheets.read_all_balances(month)
        return _emit({**data, "telegram_reply": format_sisa_all(data)}, 0 if data.get("ok") else 1)

    category = args.category
    if args.text:
        from tracker.sheets import category_from_query

        category = category_from_query(args.text) or category

    if not category and mf and mf.explicit and mf.prefix:
        data = sheets.read_all_balances(month)
        return _emit({**data, "telegram_reply": format_sisa_all(data)}, 0 if data.get("ok") else 1)

    if not category:
        return _emit(
            {
                "ok": False,
                "error": "missing_category",
                "telegram_reply": format_error(
                    "Sebut kategori: sisa daily, sisa semua, sisa transport, …"
                ),
            },
            1,
        )
    data = sheets.read_category_balance(category, month)
    return _emit({**data, "telegram_reply": format_sisa(data)}, 0 if data.get("ok") else 1)


def cmd_query(args: argparse.Namespace) -> int:
    spec = parse_query(args.text or "")
    if not spec:
        return _emit(
            {
                "ok": False,
                "error": "parse_failed",
                "telegram_reply": format_error(
                    "Contoh: sudah berapa infaq bulan ini? · berapa kali bensin? · daily lebih dari 200k"
                ),
            },
            1,
        )
    with connect(Path(args.db) if args.db else None) as conn:
        rows = search_expenses(conn, user_id=args.user_id, spec=spec)
    return _emit(
        {
            "ok": True,
            "count": len(rows),
            "telegram_reply": format_query_result(spec.label, rows),
        }
    )


def cmd_transfer(args: argparse.Namespace) -> int:
    spec = parse_transfer(args.text or "")
    if not spec:
        return _emit(
            {
                "ok": False,
                "error": "parse_failed",
                "telegram_reply": format_error(
                    "Format: pindah daily ke entertain 100k (atau: transfer ... to ...)"
                ),
            },
            1,
        )
    note_from = f"Pindah ke {spec.to_category}"
    note_to = f"Pindah dari {spec.from_category}"
    with connect(Path(args.db) if args.db else None) as conn:
        # Dari kategori sumber: +nominal (pakai anggaran daily)
        out_row = add_expense(
            conn,
            user_id=args.user_id,
            amount=spec.amount,
            category=spec.from_category,
            note=note_from,
            source="transfer",
        )
        # Ke kategori tujuan: -nominal (sisa entertain naik)
        in_row = add_expense(
            conn,
            user_id=args.user_id,
            amount=-spec.amount,
            category=spec.to_category,
            note=note_to,
            source="transfer",
        )
    sheets.sync_append(out_row)
    sheets.sync_append(in_row)
    return _emit(
        {
            "ok": True,
            "transfer": {"out": out_row, "in": in_row},
            "telegram_reply": format_transfer(out_row, in_row),
        }
    )


def cmd_help(_args: argparse.Namespace) -> int:
    return _emit({"ok": True, "telegram_reply": format_help()})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Catat pengeluaran (Hermes / Telegram).")
    p.add_argument("--db", help="Path SQLite (FINTRACKER_DB_PATH dari .env.local)")
    sub = p.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add")
    add_p.add_argument("--user-id", required=True)
    add_p.add_argument("--amount", type=int)
    add_p.add_argument("--category")
    add_p.add_argument("--note", default="")
    add_p.add_argument("--text")
    add_p.add_argument("--source")
    add_p.set_defaults(func=cmd_add)

    list_p = sub.add_parser("list")
    list_p.add_argument("--user-id", required=True)
    list_p.add_argument("--limit", type=int, default=10)
    list_p.add_argument("--month")
    list_p.set_defaults(func=cmd_list)

    sum_p = sub.add_parser("summary")
    sum_p.add_argument("--user-id", required=True)
    sum_p.add_argument("--month")
    sum_p.set_defaults(func=cmd_summary)

    undo_p = sub.add_parser("undo")
    undo_p.add_argument("--user-id", required=True)
    undo_p.set_defaults(func=cmd_undo)

    sisa_p = sub.add_parser("sisa")
    sisa_p.add_argument("--user-id", required=True)
    sisa_p.add_argument("--category", help="Daily, Transport, Primary, …")
    sisa_p.add_argument("--text", help="Pesan natural: sisa daily bulan ini")
    sisa_p.add_argument("--month", help="MAY atau 2026-05 (default: bulan ini)")
    sisa_p.add_argument("--all", action="store_true", help="Semua kategori + total")
    sisa_p.set_defaults(func=cmd_sisa)

    del_p = sub.add_parser("delete")
    del_p.add_argument("--user-id", required=True)
    del_p.add_argument("--id", type=int, required=True)
    del_p.set_defaults(func=cmd_delete)

    tr_p = sub.add_parser("transfer")
    tr_p.add_argument("--user-id", required=True)
    tr_p.add_argument("--text", required=True)
    tr_p.set_defaults(func=cmd_transfer)

    qy_p = sub.add_parser("query")
    qy_p.add_argument("--user-id", required=True)
    qy_p.add_argument("--text", required=True)
    qy_p.set_defaults(func=cmd_query)

    sub.add_parser("help").set_defaults(func=cmd_help)

    argv = _normalize_argv(list(argv) if argv is not None else sys.argv[1:])
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
