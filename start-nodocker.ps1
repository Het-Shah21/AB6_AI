<#
.SYNOPSIS
  Starts the AB6 AI Mentor + Streamlit UI **without Docker**.
  Uses pure in-process backends: SQLite (or in-memory dicts) for the
  database, and an in-process dict for the session cache. No Postgres,
  no Redis, no Docker.

.DESCRIPTION
  Switches the env vars to:
    MENTOR_BACKEND=memory
    MENTOR_SESSION_BACKEND=memory
  (or =sqlite if -UseSqlite is passed), then runs the same uvicorn +
  Streamlit pair that start-live.ps1 would have run.

  Run from the repo root:
    .\start-nodocker.ps1                # in-memory (no file, no persistence)
    .\start-nodocker.ps1 -UseSqlite     # persists to mentor_data.db
    .\start-nodocker.ps1 -WithUi        # also launches Streamlit

  To stop:
    .\stop-live.ps1
#>

[CmdletBinding()]
param(
    [switch]$UseSqlite = $false,
    [switch]$WithUi = $false,
    [switch]$SkipInstall = $false,
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Get-Location).Path
$LogDir = Join-Path $RepoRoot 'logs'
$null = New-Item -ItemType Directory -Path $LogDir -Force
$PidFile = Join-Path $RepoRoot '.runtime-pids.json'

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   [WARN] $msg" -ForegroundColor Yellow }

# --- 0. Pre-flight ---
Write-Step "Pre-flight: Python 3.11+"
$py = $null
foreach ($c in @('py','python','python3')) {
    $p = Get-Command $c -ErrorAction SilentlyContinue
    if ($p) { $py = $p.Source; break }
}
if (-not $py) {
    Write-Host "   [ERR] no python on PATH.  Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
$ver = & $py -V 2>&1
Write-Ok "using $py  ($ver)"
$venvPy = $py

# --- 1. venv + install ---
$VenvDir = Join-Path $RepoRoot '.venv'
if (-not (Test-Path $VenvDir)) {
    Write-Step "Creating venv at $VenvDir"
    & $py -m venv $VenvDir
}
$venvPy = Join-Path $VenvDir 'Scripts\python.exe'

if (-not $SkipInstall) {
    Write-Step "Installing dependencies"
    & $venvPy -m pip install --upgrade pip | Out-Null
    & $venvPy -m pip install -e ".[ui]" 2>&1 | Select-Object -Last 3
    Write-Ok "deps installed"
}

# --- 2. Env ---
Write-Step "Configuring in-process backends"
$env:MENTOR_BACKEND        = $(if ($UseSqlite) { 'sqlite' } else { 'memory' })
$env:MENTOR_SESSION_BACKEND = 'memory'
$env:MENTOR_DB_PATH        = Join-Path $RepoRoot 'mentor_data.db'
[System.Environment]::SetEnvironmentVariable('MENTOR_BACKEND',        $env:MENTOR_BACKEND,        'Process')
[System.Environment]::SetEnvironmentVariable('MENTOR_SESSION_BACKEND', $env:MENTOR_SESSION_BACKEND, 'Process')
[System.Environment]::SetEnvironmentVariable('MENTOR_DB_PATH',        $env:MENTOR_DB_PATH,        'Process')
Write-Ok "MENTOR_BACKEND=$($env:MENTOR_BACKEND)  MENTOR_SESSION_BACKEND=$($env:MENTOR_SESSION_BACKEND)"
Write-Ok "MENTOR_DB_PATH=$($env:MENTOR_DB_PATH)"

# LLM provider keys (optional).  Falls back to hard-coded text if blank.
foreach ($k in 'OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY') {
    if (-not (Test-Path "env:$k")) { Set-Item -Path "env:$k" -Value '' }
}

# --- 3. ARQ worker skipped (no real Redis) ---
Write-Step "Skipping ARQ worker (no real Redis in $env:MENTOR_BACKEND mode)"

# --- 4. Uvicorn (background) ---
Write-Step "Starting mentor_app on port $ApiPort"
Get-Process -Name 'uvicorn' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$apiLog = Join-Path $LogDir 'api.log'
$apiProc = Start-Process -FilePath $venvPy `
    -ArgumentList '-m','uvicorn','mentor_app:app','--host','0.0.0.0','--port',$ApiPort,'--no-access-log' `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $apiLog `
    -RedirectStandardError (Join-Path $LogDir 'api.err.log') `
    -PassThru -WindowStyle Hidden
Write-Ok "Mentor started (PID $($apiProc.Id), log: $apiLog)"

# --- 5. Health check ---
Write-Step "Health-checking http://127.0.0.1:${ApiPort}/healthz"
$healthy = $false
for ($i = 1; $i -le 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:${ApiPort}/healthz" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $healthy) {
    Write-Warn "API did not respond to /healthz within 20s; check logs/api.err.log"
} else {
    Write-Ok "API healthy"
}

# --- 6. Optional Streamlit ---
$pidInfoObj = @{
    api   = @{ pid = $apiProc.Id; log = $apiLog }
    ports = @{ api = $ApiPort }
}
$uiProc = $null
if ($WithUi) {
    Write-Step "Starting Streamlit UI on port $UiPort"
    Get-Process -Name 'streamlit' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $uiLog = Join-Path $LogDir 'ui.log'
    $env:MENTOR_API = "http://127.0.0.1:${ApiPort}"
    $uiProc = Start-Process -FilePath $venvPy `
        -ArgumentList '-m','streamlit','run','ui/streamlit_app.py','--server.port',$UiPort,'--server.headless','true','--browser.gatherUsageStats','false' `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $uiLog `
        -RedirectStandardError (Join-Path $LogDir 'ui.err.log') `
        -PassThru -WindowStyle Hidden
    Write-Ok "UI started (PID $($uiProc.Id), log: $uiLog)"
    $pidInfoObj.ui    = @{ pid = $uiProc.Id; log = $uiLog }
    $pidInfoObj.ports = @{ api = $ApiPort; ui = $UiPort }
}

$pidInfo = $pidInfoObj | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($PidFile, $pidInfo, [System.Text.UTF8Encoding]::new($false))

# --- 7. Summary ---
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  AB6 AI MENTOR - NO-DOCKER STACK UP" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API:       http://127.0.0.1:${ApiPort}" -ForegroundColor White
Write-Host "  Docs:      http://127.0.0.1:${ApiPort}/docs" -ForegroundColor White
Write-Host "  Backend:   $env:MENTOR_BACKEND (session: $env:MENTOR_SESSION_BACKEND)" -ForegroundColor White
if ($UseSqlite) {
    Write-Host "  SQLite:    $env:MENTOR_DB_PATH" -ForegroundColor White
}
Write-Host ""
if ($uiProc) {
    Write-Host "  UI:        http://127.0.0.1:${UiPort}" -ForegroundColor White
}
Write-Host "  Logs:      $LogDir" -ForegroundColor White
Write-Host "  PIDs:      $PidFile" -ForegroundColor White
Write-Host ""
Write-Host "  --- Try it ---" -ForegroundColor Cyan
Write-Host '  Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/mentor/cycle \' -ForegroundColor Gray
Write-Host '       -ContentType application/json \' -ForegroundColor Gray
Write-Host '       -Body (Get-Content .\sample_cycle.json -Raw)' -ForegroundColor Gray
Write-Host ""
Write-Host "  Stop with:  .\stop-live.ps1" -ForegroundColor DarkGray
