# Bot Financial Tracker

Repo: **[github.com/derwinmhrdka/bot-financial-tracker](https://github.com/derwinmhrdka/bot-financial-tracker)**

Catat pengeluaran lewat **Telegram**.

**Disarankan:** bot langsung **tanpa Gemini** (cepat, tanpa kuota 429):

```powershell
.\scripts\start-telegram-bot.ps1
```

Alternatif lama: [Hermes Agent](https://hermes-agent.nousresearch.com/) + `.\scripts\start-gateway.ps1` (pakai API Gemini).

## Struktur

```
tracker/       # CLI, SQLite, parser, format balasan Telegram
skills/        # Skill Hermes
deploy/        # Template + install
scripts/       # start-gateway.ps1
.env.local     # Secret (gitignored) — copy dari deploy/env.local.example
data/          # Database lokal
```

## Setup lokal (bot langsung — tanpa Gemini)

```powershell
copy deploy\env.local.example .env.local
# isi TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS, TELEGRAM_ADMIN_USERS (opsional)

pip install -r requirements.txt   # google-auth untuk Sheets

.\scripts\start-telegram-bot.ps1
```

**Penting:** satu token Telegram hanya untuk **satu** proses. Matikan `hermes gateway` sebelum menjalankan bot ini.

### Opsional: Hermes + Gemini

```powershell
# GOOGLE_API_KEY untuk Gemini
.\deploy\install.ps1
.\scripts\start-gateway.ps1
```

Setelah ubah skill/AGENTS: `.\deploy\install.ps1` (otomatis set `tool_progress: off` + nonaktifkan tool `skill_view`), restart gateway, di Telegram kirim `/new` lalu tes lagi.

## Perintah Telegram

| Pesan | Aksi |
|-------|------|
| `makan siang 35rb` | Catat |
| `total bulan ini` | Ringkasan |
| `list 10` | Riwayat |
| `undo` | Hapus terakhir |
| `sisa daily` / `sisa semua` | Sisa anggaran (sheet MAY/JUNE) |
| `hapus #12` | Hapus transaksi by id (+ sheet) |
| `pindah daily ke entertain 100k` | Pindah saldo (Daily +100k, Entertain -100k) |
| `sudah berapa infaq bulan ini?` | Cari riwayat bulan ini (default) |
| `berapa kali bensin?` | Cari bulan berjalan (bukan semua waktu) |
| `infaq bulan lalu` / `infaq bulan mei` | Filter bulan tertentu |
| `bensin semua bulan` | Cari tanpa batas bulan |
| `daily lebih dari 200k` | Filter kategori + nominal |
| `makan 35rb kemarin` / `infaq 50k 15 mei` | Catat dengan tanggal lampau |
| `bantuan` | Panduan |

### Kelola user (admin saja)

Daftar disimpan di `data/allowed_users.json` (dibuat dari `.env.local` saat pertama jalan).

| Perintah (admin) | Aksi |
|------------------|------|
| `tambah user 123456789` | Izinkan user baru |
| `hapus user 123456789` | Cabut akses |
| `list user` | Lihat semua user |

Admin default: `TELEGRAM_ADMIN_USERS`, atau user pertama di `TELEGRAM_ALLOWED_USERS`.

User baru: minta ID dari [@userinfobot](https://t.me/userinfobot).

### Grup Telegram

- Tambahkan bot ke grup; yang boleh pakai = user di **list user** (bukan ID grup).
- Setiap orang catat pengeluaran **sendiri** (pakai user id masing-masing).
- Di grup bot **diam** untuk obrolan biasa; hanya merespons jika pesan mirip tracker (mis. `makan 35rb`, `sisa daily`, `list`, `undo`). Reply ke pesan bot juga dianggap perintah.
- Opsional: `TELEGRAM_GROUP_REQUIRE_MENTION=true` jika mau wajib @bot.
- **Wajib:** @BotFather → bot kamu → **Bot Settings → Group Privacy → Turn off**. Kalau privacy aktif, Telegram tidak mengirim pesan biasa (`makan 35rb`) ke bot — hanya `/command` atau @mention.

Balasan siap kirim ada di field **`telegram_reply`** dari CLI (Hermes mengirim teks itu ke chat).

## Error Gemini HTTP 429 (quota)

Pesan seperti `RESOURCE_EXHAUSTED` / `limit: 20` pada **gemini-2.5-flash** = kuota **free tier** Google AI Studio habis (±20 request/menit per model), bukan bug tracker/Sheets.

**Langkah cepat:**

1. Tunggu ~20–60 detik, lalu kirim lagi (atau `/new` lalu satu pesan).
2. Kurangi beban: setiap chat memicu beberapa panggilan model (tool terminal, dll.) — jangan spam banyak pesan berturut-turut.
3. Cek pemakaian: https://ai.dev/rate-limit
4. **Opsi A — billing:** Google AI Studio → aktifkan billing / tier berbayar untuk limit lebih tinggi.
5. **Opsi B — ganti model** di `%LOCALAPPDATA%\hermes\config.yaml`:

```yaml
model:
  default: gemini-2.0-flash
  provider: gemini
```

Lalu restart gateway. (Limit per model bisa berbeda; 2.5-flash free tier paling sering kena 429 saat testing.)

**Tetap catat tanpa Telegram:** CLI langsung tidak pakai Gemini:

```powershell
python track.py add --user-id telegram:1103187440 --text "makan 35rb"
```

`httpx.ReadError` di log Telegram = gangguan jaringan sementara; gateway reconnect otomatis (~5s), biasanya terpisah dari error 429.

## VPS (Linux + GitHub Actions)

Panduan lengkap: **[deploy/DEPLOY.md](deploy/DEPLOY.md)** (Termius + push ke `main` → deploy otomatis).

```bash
export GITHUB_REPO=https://github.com/derwinmhrdka/bot-financial-tracker.git
```

Ringkas:

1. Repo: [derwinmhrdka/bot-financial-tracker](https://github.com/derwinmhrdka/bot-financial-tracker) (tanpa `.env.local` / `secrets/` di git).
2. Di VPS: `GITHUB_REPO=... bash deploy/vps-install.sh`
3. Isi `.env.local` + upload service account JSON di server.
4. GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
5. `sudo systemctl start fintracker-bot`

Alternatif Hermes: `deploy/install.sh` + `deploy/config.snippet.yaml`.

## Airafin dashboard (Phase 2)

Bot bisa sinkron ke **[airafin-dashboard](https://github.com/derwinmhrdka/airafin-dashboard)** (PostgreSQL + web UI) lewat REST API.

```env
AIRAFIN_API_ENABLED=true
AIRAFIN_API_URL=http://localhost:3081
API_SECRET_TOKEN=change-me-in-production
AIRAFIN_DEFAULT_STATUS=Done
FINTRACKER_DEFAULT_PIC=Derwin
```

| Aksi bot | Sinkron dashboard |
|----------|-------------------|
| `makan 35rb` | `POST /api/transactions` (header `X-API-Token`) |
| `undo` / `hapus #12` | `DELETE /api/transactions/:id` (id dashboard disimpan di SQLite `backend_id`) |
| `sisa daily` / `sisa semua` | `GET /api/dashboard/summary?period=June+2026` |
| `pindah daily ke entertain 100k` | Hanya lokal (belum ke API) |

**Penting:** jika `AIRAFIN_API_ENABLED=true`, matikan `GOOGLE_SHEETS_ENABLED` di bot — backend dashboard yang menulis ke Sheets (hindari baris duplikat).

Mapping otomatis:

- Kategori bot → nama Mahardiora (`Daily`, `Transport`, …) → `categoryId` dari `GET /api/categories`
- Tanggal → `date` + `period` (`June 2026`)
- Suffix `-A` / `- Anggita` → `pic: Anggita`; `-D` / `- Derwin` → `pic: Derwin`

`API_SECRET_TOKEN` harus sama dengan backend dashboard (`docker-compose` / `.env`).

## Google Sheets (opsional)

SQLite tetap sumber utama. Setiap **add** / **undo** bisa disalin ke spreadsheet.

1. [Google Cloud Console](https://console.cloud.google.com/) → buat project → aktifkan **Google Sheets API**
2. **IAM → Service Accounts** → buat akun → **Keys** → unduh JSON
3. Simpan JSON ke `secrets/google-service-account.json` (folder di-gitignore)
4. Buat Google Spreadsheet → **Share** ke email service account (Editor)
5. Copy **Spreadsheet ID** dari URL: `https://docs.google.com/spreadsheets/d/<ID>/edit`
6. Di `.env.local`:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=<ID>
GOOGLE_SERVICE_ACCOUNT_FILE=./secrets/google-service-account.json
GOOGLE_SHEETS_WORKSHEET=Pengeluaran
```

7. Pasang `google-auth` di Python yang dipakai Hermes untuk `track.py` (biasanya venv Hermes):

```powershell
# jika venv belum punya pip:
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe" -m ensurepip --upgrade
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe" -m pip install -r requirements.txt
```

**Layout `detail`** (spreadsheet existing, tab mis. `DETAIL`):

| A Date | B Category | C Detail | D Cost | E Periode | F (#id) | G (nama) |
|--------|------------|----------|--------|-----------|---------|----------|
| 2026-05-22 | Daily | Makan siang | 35000 | May | 12 | Anggita |

Akhiran pesan: `- Anggita`, `-A`, `- D` → kolom **G** (teks setelah `-`, tanpa ubah).

- `Category` Mahardiora: **Primary** (listrik, air, wifi, infaq, IPL, zakat, sedekah, kur mobil, …), **Maintenance** (bengkel, cuci AC, keran, kabel, …), **Savings** (tabungan, reksadana, emas), **Daily** (belanja, indomaret, makanan), **Transport**, dll. (default `Daily`)
- `Periode`: nama bulan Inggris dari tanggal (`April`, `May`, …)
- Kolom **F** = id bot (`#10`, `#11`, …) supaya Sheets tidak mengubah angka jadi tanggal. Hapus manual baris duplikat lama jika agent sempat retry 2×.

**Sisa anggaran:** tab bulan (`MAY`, `JUNE`, …) baris 2+ — kolom A kategori, B PLAN, D terpakai, E SISA. Contoh CLI:

```powershell
python track.py sisa --user-id telegram:1103187440 --text "sisa daily bulan ini"
```

**Layout `default`**: 8 kolom internal (`GOOGLE_SHEETS_LAYOUT=default`).

Jika Sheets gagal, catatan tetap masuk SQLite.

`GOOGLE_API_KEY` (Gemini) **berbeda** dari service account Sheets.

## Tes CLI

```powershell
python -m tracker add --user-id telegram:USER_ID --text "makan 35rb"
python -m tracker summary --user-id telegram:USER_ID
```
