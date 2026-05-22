$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$HermesDir = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA "hermes" }

if (-not (Test-Path $HermesDir)) {
    Write-Host "Jalankan hermes setup dulu."
    exit 1
}

New-Item -ItemType Directory -Path (Join-Path $HermesDir "skills") -Force | Out-Null
$dst = Join-Path $HermesDir "skills\financial-tracker"
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
Copy-Item -Recurse (Join-Path $Repo "skills\financial-tracker") $dst
Copy-Item -Force (Join-Path $Repo "deploy\AGENTS.md") (Join-Path $HermesDir "AGENTS.md")
Copy-Item -Force (Join-Path $Repo "deploy\SOUL.md") (Join-Path $HermesDir "SOUL.md")
[System.IO.File]::WriteAllText(
    (Join-Path $HermesDir "gateway.json"),
    '{"platforms":{"telegram":{"enabled":true}}}',
    [System.Text.UTF8Encoding]::new($false)
)

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    $venvPy = Join-Path $HermesDir "hermes-agent\venv\Scripts\python.exe"
    if (Test-Path $venvPy) { $py = @{ Source = $venvPy } }
}
if ($py) {
    & $py.Source (Join-Path $Repo "deploy\patch_hermes_config.py") $Repo
} else {
    Write-Host 'WARN: python tidak ada - set manual tool_progress=off dan disabled_toolsets skills'
}

Write-Host "Lalu: .\scripts\start-gateway.ps1"
