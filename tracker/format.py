"""Format balasan singkat untuk Telegram."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def format_idr(amount: int) -> str:
    n = int(amount)
    s = f"{abs(n):,}".replace(",", ".")
    return f"-Rp {s}" if n < 0 else f"Rp {s}"


def format_transfer(from_row: dict[str, Any], to_row: dict[str, Any]) -> str:
    amt = abs(int(from_row["amount"]))
    return (
        f"✅ Pindah saldo {format_idr(amt)}\n"
        f"📤 {from_row.get('category')}: {format_idr(int(from_row['amount']))} · #{from_row['id']}\n"
        f"📥 {to_row.get('category')}: {format_idr(int(to_row['amount']))} · #{to_row['id']}"
    )


def format_add(expense: dict[str, Any]) -> str:
    cat = expense.get("category") or "lainnya"
    note = (expense.get("note") or "").strip() or "—"
    who = (expense.get("attributed_to") or "").strip()
    lines = [
        "✅ Pengeluaran tercatat",
        f"📝 {note}",
        f"💰 {format_idr(int(expense['amount']))}",
        f"🏷 {cat}",
    ]
    if who:
        lines.append(f"👤 {who}")
    created = str(expense.get("created_at") or "")
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if dt.date() != datetime.now(dt.tzinfo).date():
                lines.append(f"📅 {_short_date(created)}")
        except ValueError:
            pass
    lines.append(f"🆔 #{expense['id']}")
    return "\n".join(lines)


def format_summary(data: dict[str, Any]) -> str:
    month = data.get("month", "")
    total = data.get("formatted_total") or format_idr(int(data["total"]))
    count = int(data["count"])
    lines = [
        f"📊 Ringkasan {month}",
        f"💰 Total: {total}",
        f"📌 {count} transaksi",
    ]
    by_cat = data.get("by_category") or []
    if by_cat:
        lines.append("")
        lines.append("Per kategori:")
        for row in by_cat[:5]:
            lines.append(
                f"• {row['category']}: {format_idr(int(row['total']))} ({row['count']}x)"
            )
    return "\n".join(lines)


def _short_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m %H:%M")
    except ValueError:
        return iso[:16]


def format_list(rows: list[dict[str, Any]], *, month: str | None = None) -> str:
    if not rows:
        hint = f" ({month})" if month else ""
        return f"📭 Belum ada pengeluaran{hint}."

    title = f"📋 Riwayat ({len(rows)} terakhir)"
    if month:
        title += f" — {month}"
    lines = [title, ""]
    for row in rows:
        note = (row.get("note") or "").strip() or "—"
        cat = row.get("category") or "lainnya"
        who = (row.get("attributed_to") or "").strip()
        who_bit = f" · {who}" if who else ""
        lines.append(
            f"#{row['id']} {_short_date(row['created_at'])}\n"
            f"   {note} · {format_idr(int(row['amount']))} · {cat}{who_bit}"
        )
    return "\n".join(lines)


def format_delete(removed: dict[str, Any] | None, expense_id: int) -> str:
    if not removed:
        return f"❌ Gagal hapus #{expense_id}."
    return (
        f"🗑️ Dihapus #{expense_id}\n"
        f"📝 {(removed.get('note') or '—')}\n"
        f"💰 {format_idr(int(removed['amount']))}"
    )


def format_undo(removed: dict[str, Any] | None) -> str:
    if not removed:
        return "❌ Tidak ada data untuk dihapus."
    return (
        "↩️ Entri terakhir dihapus\n"
        f"📝 {(removed.get('note') or '—')}\n"
        f"💰 {format_idr(int(removed['amount']))}\n"
        f"🆔 #{removed['id']}"
    )


def format_error(message: str) -> str:
    return (
        f"❌ {message}\n\n"
        "Format contoh:\n"
        "• makan siang 35rb\n"
        "• gojek 15k\n"
        "• total bulan ini\n"
        "• list 10\n"
        "• undo"
    )


def format_sisa_all(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        sheet = data.get("month_sheet") or ""
        if data.get("error") == "sheets_disabled":
            return "❌ Google Sheets tidak aktif."
        if data.get("error") == "sheets_config":
            d = data.get("detail") or "cek .env.local & file secrets/*.json di VPS"
            return f"❌ Sheets config: {d}"
        return f"❌ Tidak bisa baca sisa ({data.get('error', 'error')}) {sheet}.".strip()

    sheet = data.get("month_sheet", "")
    lines = [f"📊 Sisa semua kategori — {sheet}", ""]
    for row in data.get("categories") or []:
        rem = int(row.get("remaining") or 0)
        lines.append(f"• {row['category']}: {format_idr(rem)}")
    grand = data.get("grand_total")
    if grand:
        lines.append("")
        lines.append(
            f"Σ Total sisa: {format_idr(int(grand.get('remaining') or 0))} "
            f"(plan {format_idr(int(grand.get('plan') or 0))})"
        )
    return "\n".join(lines)


def format_sisa(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        cat = data.get("category") or "?"
        sheet = data.get("month_sheet") or ""
        if data.get("error") == "not_found":
            return f"❌ Kategori '{cat}' tidak ditemukan di sheet {sheet}."
        if data.get("error") == "sheets_disabled":
            return "❌ Google Sheets tidak aktif."
        if data.get("error") == "sheets_config":
            d = data.get("detail") or "cek .env.local & secrets/*.json"
            return f"❌ Sheets config: {d}"
        return f"❌ Tidak bisa baca sisa ({data.get('error', 'error')})."

    cat = data["category"]
    sheet = data.get("month_sheet", "")
    plan = format_idr(int(data.get("plan") or 0))
    spent = format_idr(int(data.get("spent") or 0))
    sisa = format_idr(int(data.get("remaining") or 0))
    return (
        f"📉 Sisa {cat} — {sheet}\n"
        f"📋 Anggaran (PLAN): {plan}\n"
        f"💸 Terpakai: {spent}\n"
        f"✅ Sisa: {sisa}"
    )


def _query_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except ValueError:
        return (iso or "")[:10]


def format_query_result(spec_label: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"📭 Tidak ada data untuk: {spec_label}"

    total = sum(int(r.get("amount") or 0) for r in rows)
    lines = [
        f"📊 {spec_label}",
        f"{len(rows)} transaksi · total {format_idr(total)}",
        "",
    ]
    for row in rows[:25]:
        note = (row.get("note") or "").strip() or "—"
        cat = (row.get("category") or "").strip()
        cat_bit = f" · {cat}" if cat else ""
        who = (row.get("attributed_to") or "").strip()
        who_bit = f" · {who}" if who else ""
        lines.append(
            f"• {_query_date(str(row.get('created_at', '')))} — "
            f"{format_idr(int(row['amount']))} · {note}{cat_bit}{who_bit} (#{row['id']})"
        )
    if len(rows) > 25:
        lines.append(f"\n… +{len(rows) - 25} transaksi lagi (pakai list)")
    return "\n".join(lines)


def format_help() -> str:
    return (
        "💡 Bot Catat Pengeluaran\n\n"
        "Kirim pesan seperti:\n"
        "• makan siang 35rb\n"
        "• kopi 25rb\n"
        "• gojek 15k ke kantor\n\n"
        "Perintah:\n"
        "• total — ringkasan DB\n"
        "• sisa daily / sisa semua — anggaran (Google Sheet)\n"
        "• sisa juni / sisa daily juni — sisa per bulan\n"
        "• Kategori di pesan: entertain jus 10k · jus 10k daily · transport gojek 25rb\n"
        "• Nama di akhir (kolom G): makan 35rb - Anggita · jus 10k -A · kopi 5rb - D\n"
        "• Pindah saldo: pindah daily ke entertain 100k\n"
        "• Tanggal: makan 35rb kemarin · infaq 50k 15 mei · kopi 20rb tgl 10\n"
        "• Tanya: berapa kali bensin? (bulan ini) · infaq bulan lalu · daily lebih dari 200k · semua bulan\n"
        "• list 10 — riwayat\n"
        "• undo — hapus terakhir\n"
        "• hapus #12 — hapus by id\n\n"
        "Admin:\n"
        "• tambah user 123456789\n"
        "• hapus user 123456789\n"
        "• list user\n"
    )
