---
name: financial-tracker
description: Catat pengeluaran; pakai track.py (path absolut), balas telegram_reply saja.
version: 1.2.0
metadata:
  hermes:
    tags: [Finance, Indonesia]
    config:
      - key: skills.config.financial_tracker.repo_path
        description: Path absolut root repo (folder berisi track.py)
        default: ""
        prompt: Path repo bot-financial-tracker
---

# Financial Tracker

Hermes harus memanggil **`track.py`** dengan path absolut — bukan `python -m tracker`.

## Perintah

```bash
python REPO/track.py add --user-id telegram:USER_ID --text "PESAN" --source telegram
python REPO/track.py summary --user-id telegram:USER_ID
python REPO/track.py list --user-id telegram:USER_ID --limit 10
python REPO/track.py undo --user-id telegram:USER_ID
```

`REPO` = `skills.config.financial_tracker.repo_path` (contoh: `D:/derwin.mahardika-iu/git/bot-financial-tracker`).

## Balasan

Kirim **hanya** `telegram_reply` dari JSON stdout. Jangan skill_view. Jangan tampilkan output terminal ke user.
