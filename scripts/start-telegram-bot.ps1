# Bot Telegram langsung — tanpa Hermes / Gemini
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$EnvLocal = Join-Path $Repo ".env.local"

if (-not (Test-Path $EnvLocal)) {
    Write-Host "Buat: copy deploy\env.local.example .env.local"
    exit 1
}

foreach ($line in Get-Content $EnvLocal -Encoding UTF8) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $n, $v = $line -split '=', 2
    $n = $n.Trim().TrimStart([char]0xFEFF)
    [Environment]::SetEnvironmentVariable($n, $v.Trim(), "Process")
}

Write-Host "Telegram bot (no Gemini) | Repo: $Repo"
Write-Host "Stop Hermes gateway dulu agar tidak bentrok polling token."
Set-Location $Repo
python -m tracker.telegram_bot
