# Deploy ke VPS (Termius + GitHub Actions)

**Repo:** [github.com/derwinmhrdka/bot-financial-tracker](https://github.com/derwinmhrdka/bot-financial-tracker)

Bot jalan 24/7 dengan **systemd** + deploy otomatis setiap push ke branch `main`.

## Ringkasan

| Langkah | Di mana |
|---------|---------|
| 1. Kode di GitHub | Sudah: `derwinmhrdka/bot-financial-tracker` |
| 2. Setup VPS sekali | Termius (SSH) |
| 3. Secret bot | `.env.local` + `secrets/*.json` **hanya di VPS** |
| 4. GitHub Actions Secrets | `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` |
| 5. Deploy otomatis | Setiap `git push origin main` |

---

## Bagian A — GitHub (PC Windows)

Repo kamu: **https://github.com/derwinmhrdka/bot-financial-tracker**

### Clone baru / PC lain

```powershell
git clone https://github.com/derwinmhrdka/bot-financial-tracker.git
cd bot-financial-tracker
copy deploy\env.local.example .env.local
# edit .env.local (jangan di-commit)
```

### Project lokal sudah ada (sync ke GitHub)

```powershell
cd D:\derwin.mahardika-iu\git\bot-financial-tracker

git remote -v
# Kalau belum ada origin:
git remote add origin https://github.com/derwinmhrdka/bot-financial-tracker.git

git add .
git status
# Pastikan TIDAK ada: .env.local, secrets/, data/*.db

git commit -m "pesan commit kamu"
git branch -M main
git push -u origin main
```

SSH (opsional):

```powershell
git remote set-url origin git@github.com:derwinmhrdka/bot-financial-tracker.git
git push -u origin main
```

### Cek Actions

Setelah push: https://github.com/derwinmhrdka/bot-financial-tracker/actions

---

## Bagian B — VPS sekali (Termius)

### 1. Koneksi SSH di Termius

| Field | Nilai |
|-------|--------|
| Label | `fintracker-vps` |
| Address | IP VPS kamu |
| Port | `22` |
| Username | `deploy` (disarankan) atau `root` untuk setup pertama |
| Key / Password | sesuai VPS |

**Tidak ada user `ubuntu`?** Normal di beberapa VPS (cuma `root`). Dua opsi:

**Opsi A — Login `root`, script buat user `deploy` otomatis:**

```bash
whoami   # root
cd /tmp/bot-financial-tracker   # setelah git clone
export GITHUB_REPO=https://github.com/derwinmhrdka/bot-financial-tracker.git
export APP_DIR=/opt/bot-financial-tracker
bash deploy/vps-install.sh
```

Lalu di Termius ganti username ke **`deploy`** untuk SSH berikutnya. GitHub Secret `VPS_USER` = `deploy`.

**Opsi B — Buat user manual dari root:**

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
su - deploy
```

Lanjut install sebagai `deploy` (bukan root).

### 2. Install & clone (copy-paste di VPS)

```bash
export GITHUB_REPO=https://github.com/derwinmhrdka/bot-financial-tracker.git
export APP_DIR=/opt/bot-financial-tracker

cd /tmp
git clone "$GITHUB_REPO" bot-financial-tracker
cd bot-financial-tracker
chmod +x deploy/*.sh
GITHUB_REPO="$GITHUB_REPO" APP_DIR="$APP_DIR" bash deploy/vps-install.sh
```

### 3. `.env.local` di server

```bash
nano /opt/bot-financial-tracker/.env.local
```

Contoh (sesuaikan token & sheet ID):

```env
TELEGRAM_BOT_TOKEN=isi_dari_botfather
TELEGRAM_ALLOWED_USERS=1103187440
TELEGRAM_ADMIN_USERS=1103187440
TELEGRAM_GROUP_REQUIRE_MENTION=false

FINTRACKER_DB_PATH=/opt/bot-financial-tracker/data/expenses.db

GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=1G3zUbKKBKLou2-_1I0dtcFZItub7HiaQawIb72Wl-yc
GOOGLE_SERVICE_ACCOUNT_FILE=/opt/bot-financial-tracker/secrets/google-service-account.json
GOOGLE_SHEETS_WORKSHEET=DETAIL
GOOGLE_SHEETS_LAYOUT=detail
GOOGLE_SHEETS_CATEGORY_DEFAULT=Daily
```

### 4. Upload service account (Termius SFTP)

- Host: IP VPS yang sama
- Path di server: `/opt/bot-financial-tracker/secrets/`
- File: JSON dari Google Cloud (mis. `google-service-account.json`)

Lalu di SSH:

```bash
sudo chown -R ubuntu:ubuntu /opt/bot-financial-tracker/secrets
sudo chown ubuntu:ubuntu /opt/bot-financial-tracker/.env.local
sudo chmod 600 /opt/bot-financial-tracker/.env.local
```

(Ganti `deploy` / `ubuntu` sesuai user SSH kamu.)

### 5. Start bot

```bash
sudo systemctl start fintracker-bot
sudo systemctl status fintracker-bot
journalctl -u fintracker-bot -f
```

Log sukses: `Bot aktif @nama_bot ...`

**Matikan bot di PC** (`start-telegram-bot.ps1` / Hermes) — satu token Telegram = satu proses.

---

## Bagian C — GitHub Actions

Settings repo: https://github.com/derwinmhrdka/bot-financial-tracker/settings/secrets/actions

### 1. Buat SSH key deploy (PC Windows)

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\fintracker_deploy" -N '""'
notepad "$env:USERPROFILE\.ssh\fintracker_deploy.pub"
notepad "$env:USERPROFILE\.ssh\fintracker_deploy"
```

- **`.pub`** → paste ke VPS `~/.ssh/authorized_keys`
- **Tanpa .pub** → GitHub Secret `VPS_SSH_KEY` (semua baris termasuk `BEGIN`/`END`)

Di VPS:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
# paste public key, simpan
chmod 600 ~/.ssh/authorized_keys
```

### 2. Repository Secrets (wajib)

| Name | Value |
|------|--------|
| `VPS_HOST` | IP VPS, mis. `123.45.67.89` |
| `VPS_USER` | `deploy` atau user SSH Termius (bukan `root`) |
| `VPS_SSH_KEY` | isi private key `fintracker_deploy` |

Opsional:

| Name | Value |
|------|--------|
| `VPS_PORT` | `22` |
| `VPS_APP_DIR` | `/opt/bot-financial-tracker` |

### 3. Tes deploy

```powershell
cd D:\derwin.mahardika-iu\git\bot-financial-tracker
git add .
git commit -m "test deploy"
git push origin main
```

Buka: https://github.com/derwinmhrdka/bot-financial-tracker/actions → workflow **Deploy to VPS** harus hijau.

Deploy manual: **Actions → Deploy to VPS → Run workflow**.

---

## Bagian D — Operasi harian

| Perintah (VPS) | Fungsi |
|----------------|--------|
| `journalctl -u fintracker-bot -f` | Log live |
| `sudo systemctl restart fintracker-bot` | Restart |
| `sudo systemctl stop fintracker-bot` | Stop |

Update kode: edit di PC → `git push origin main` → Actions restart otomatis.

---

## Troubleshooting

| Gejala | Solusi |
|--------|--------|
| Actions gagal SSH | Cek `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, firewall port 22 |
| `Permission denied (publickey)` | Public key belum di `authorized_keys` |
| `Conflict: terminated by other getUpdates` | Stop bot di PC, `sudo systemctl restart fintracker-bot` |
| Bot tidak balas | `journalctl -u fintracker-bot -n 50` |
| Sheets gagal | Path JSON benar + spreadsheet di-share ke email service account |
| `git pull` gagal di Actions | `sudo chown -R ubuntu:ubuntu /opt/bot-financial-tracker` |

---

## File deploy

| File | Fungsi |
|------|--------|
| `deploy/vps-install.sh` | Setup sekali di VPS |
| `deploy/remote-deploy.sh` | `pip install` + restart (Actions) |
| `deploy/fintracker-bot.service` | Unit systemd |
| `deploy/start-bot.sh` | Muat `.env.local`, jalankan bot |
| `.github/workflows/deploy.yml` | Workflow deploy |

**Repo clone URL:** `https://github.com/derwinmhrdka/bot-financial-tracker.git`
