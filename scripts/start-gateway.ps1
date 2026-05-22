# Muat .env.local lalu jalankan Hermes gateway
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$EnvLocal = Join-Path $Repo ".env.local"
$HermesDir = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA "hermes" }

if (-not (Test-Path $EnvLocal)) {
    Write-Host "Buat: copy deploy\env.local.example .env.local"
    exit 1
}

foreach ($line in Get-Content $EnvLocal) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $n, $v = $line -split '=', 2
    [Environment]::SetEnvironmentVariable($n.Trim(), $v.Trim(), "Process")
}

$env:HERMES_HOME = $HermesDir
$Keys = @{}
Get-Content $EnvLocal | Where-Object { $_ -match '^(TELEGRAM_|GOOGLE_|GEMINI_|FINTRACKER_)' } | ForEach-Object {
    $n, $v = $_ -split '=', 2
    $Keys[$n.Trim()] = $v.Trim()
}
$HermesEnv = Join-Path $HermesDir ".env"
$Out = @()
if (Test-Path $HermesEnv) {
    Get-Content $HermesEnv | ForEach-Object {
        if ($_ -notmatch '=') { $Out += $_; return }
        if (-not $Keys.ContainsKey(($_ -split '=', 2)[0].Trim())) { $Out += $_ }
    }
}
$Out += "# synced from .env.local"
$Keys.GetEnumerator() | ForEach-Object { $Out += "$($_.Key)=$($_.Value)" }
$Out | Set-Content $HermesEnv -Encoding UTF8

Write-Host "Gateway: $HermesDir | Repo: $Repo"
hermes gateway
