# Deploy ke VPS (Termius + GitHub Actions)

Bot jalan 24/7 dengan **systemd** + deploy otomatis setiap push ke branch `main`.

## Ringkasan

1. Push repo ke **GitHub** (tanpa secret).
2. Setup **VPS sekali** lewat Termius (SSH).
3. Pasang **GitHub Secrets** untuk SSH deploy.
4. Setiap `git push` → Actions pull + restart bot.

---

## Bagian A — GitHub (dari PC Windows)

### 1. Buat repo di GitHub

- https://github.com/new
- Nama misalnya `bot-financial-tracker`
- **Private** (disarankan)
- Jangan centang README/license (repo lokal sudah ada isinya)

### 2. Push kode pertama kali

Di PowerShell, folder project:

```powershell
cd D:\derwin.mahardika-iu\git\bot-financial-tracker

git init
git add .
git status
# Pastikan TIDAK ada: .env.local, secrets/, data/*.db

git commit -m "Initial commit: financial tracker Telegram bot"
git branch -M main
git remote add origin https://github.com/USERNAME/bot-financial-tracker.git
git push -u origin main
```

Ganti `USERNAME` dengan akun GitHub kamu.

> Kalau pakai SSH GitHub: `git@github.com:USERNAME/bot-financial-tracker.git`

---

## Bagian B — VPS sekali (Termius)

### 1. Koneksi SSH

- Buka **Termius** → New Host
- Address = IP VPS, User = `ubuntu` / `root` (sesuai provider)
- Authentication = password atau SSH key

### 2. Pasang dependensi & clone repo

```bash
# Ganti URL repo kamu
export GITHUB_REPO=https://github.com/USERNAME/bot-financial-tracker.git
export APP_DIR=/opt/bot-financial-tracker

cd /tmp
git clone "$GITHUB_REPO" bot-financial-tracker
cd bot-financial-tracker
chmod +x deploy/*.sh
GITHUB_REPO="$GITHUB_REPO" APP_DIR="$APP_DIR" bash deploy/vps-install.sh
```

### 3. Secret di server (tidak lewat GitHub)

```bash
sudo nano /opt/bot-financial-tracker/.env.local
```

Isi minimal (path **absolut** di Linux):

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USERS=1103187440
TELEGRAM_ADMIN_USERS=1103187440
TELEGRAM_GROUP_REQUIRE_MENTION=false

FINTRACKER_DB_PATH=/opt/bot-financial-tracker/data/expenses.db

GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_FILE=/opt/bot-financial-tracker/secrets/google-service-account.json
GOOGLE_SHEETS_WORKSHEET=DETAIL
GOOGLE_SHEETS_LAYOUT=detail
GOOGLE_SHEETS_CATEGORY_DEFAULT=Daily
```

Upload JSON service account (Termius **SFTP** / file transfer):

```bash
sudo mkdir -p /opt/bot-financial-tracker/secrets
# upload file .json ke folder secrets/
sudo chown -R ubuntu:ubuntu /opt/bot-financial-tracker/secrets
sudo chown ubuntu:ubuntu /opt/bot-financial-tracker/.env.local
sudo chmod 600 /opt/bot-financial-tracker/.env.local
```

### 4. Jalankan bot

```bash
sudo systemctl start fintracker-bot
sudo systemctl status fintracker-bot
journalctl -u fintracker-bot -f
```

Log sukses: `Bot aktif @nama_bot ...`

**Matikan bot di PC** (`start-telegram-bot.ps1` / Hermes) — satu token hanya satu proses.

---

## Bagian C — GitHub Actions (deploy otomatis)

### 1. SSH key khusus deploy

Di **PC** (PowerShell):

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\fintracker_deploy" -N '""'
```

- Public key: `fintracker_deploy.pub` → tambahkan ke VPS:

```bash
# di VPS (Termius)
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# paste isi fintracker_deploy.pub, simpan
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

- Private key: isi file `fintracker_deploy` (tanpa .pub) → untuk GitHub Secret.

### 2. Repository Secrets

Repo GitHub → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Contoh |
|--------|--------|
| `VPS_HOST` | `123.45.67.89` |
| `VPS_USER` | `ubuntu` |
| `VPS_SSH_KEY` | isi penuh private key `fintracker_deploy` |
| `VPS_PORT` | `22` (opsional) |
| `VPS_APP_DIR` | `/opt/bot-financial-tracker` (opsional) |

### 3. Izin git pull di VPS

`VPS_USER` di GitHub Secrets harus **sama** dengan user yang memiliki folder app (biasanya `ubuntu`).

Setelah push ke `main`, cek tab **Actions** di GitHub. Hijau = deploy OK.

Deploy manual: **Actions → Deploy to VPS → Run workflow**.

---

## Bagian D — Operasi harian

| Perintah | Fungsi |
|----------|--------|
| `journalctl -u fintracker-bot -f` | Lihat log live |
| `sudo systemctl restart fintracker-bot` | Restart manual |
| `sudo systemctl stop fintracker-bot` | Stop |

Update kode: edit di PC → commit → push `main` → Actions deploy otomatis.

---

## Troubleshooting

| Gejala | Solusi |
|--------|--------|
| Actions gagal SSH | Cek `VPS_HOST`, key di `authorized_keys`, port firewall |
| `Conflict: terminated by other getUpdates` | Hentikan bot di PC, restart di VPS |
| Bot tidak balas | `journalctl -u fintracker-bot -n 50` |
| Sheets gagal | Path JSON & share spreadsheet ke service account |
| Permission denied pada git pull | `chown` folder app ke user SSH deploy |

---

## File deploy

| File | Fungsi |
|------|--------|
| `deploy/vps-install.sh` | Setup sekali |
| `deploy/remote-deploy.sh` | Pull + pip + restart |
| `deploy/fintracker-bot.service` | systemd unit |
| `deploy/start-bot.sh` | Muat `.env.local`, jalankan bot |
| `.github/workflows/deploy.yml` | GitHub Actions |
