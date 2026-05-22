# Financial Tracker (Telegram)

Bot pencatat pengeluaran. **Jangan** `skill_view` / `skill_list` — langsung jalankan `track.py`.

## Jalankan CLI (WAJIB)

`REPO` = `skills.config.financial_tracker.repo_path` (contoh: `D:/derwin.mahardika-iu/git/bot-financial-tracker`).

**Jangan** `python -m tracker` — selalu `python REPO/track.py`.

Format **persis** — subcommand `add` di awal, `--text` untuk pesan user:

```bash
python REPO/track.py add --user-id telegram:CHAT_ID --text "PESAN_USER" --source telegram
python REPO/track.py summary --user-id telegram:CHAT_ID
python REPO/track.py list --user-id telegram:CHAT_ID --limit 10
python REPO/track.py undo --user-id telegram:CHAT_ID
python REPO/track.py sisa --user-id telegram:CHAT_ID --text "sisa daily bulan ini"
python REPO/track.py help
```

`CHAT_ID` = **hanya angka** user/chat Telegram (DM = user id, contoh `1103187440`). Bukan nama, bukan session id.

## Balasan ke user (WAJIB)

1. Jalankan perintah di atas.
2. Baca JSON stdout, ambil **`telegram_reply`**.
3. Kirim **hanya** teks `telegram_reply` — tanpa penjelasan tool, tanpa isi skill, tanpa output terminal mentah.

## Pemetaan pesan

| Pesan user                    | Perintah                    |
| ----------------------------- | --------------------------- |
| Ada nominal (35rb, 15k, …)    | `track.py add --text "..."` |
| total / ringkasan / bulan ini | `track.py summary`          |
| sisa daily / sisa transport … | `track.py sisa --text "..."` (baca sheet MAY/JUNE) |
| list / riwayat                | `track.py list --limit 10`  |
| undo / hapus terakhir         | `track.py undo`             |
| bantuan / help                | `track.py help`             |

## Larangan

- Jangan `skill_view` / jangan tampilkan isi SKILL.md ke user.
- Jangan kirim log terminal atau JSON ke user.
- Jangan mengarang angka.
