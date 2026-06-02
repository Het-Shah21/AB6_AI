<#
.SYNOPSIS
  Brings up the AB6 AI agent stack with real infrastructure (Postgres, Redis,
  ARQ worker, FastAPI). Idempotent - safe to re-run.

.DESCRIPTION
  Performs:
    1. Pre-flight checks (Docker, Python 3.11+)
    2. docker compose up -d postgres redis
    3. Waits for Postgres + Redis health
    4. Creates .venv, installs deps
    5. Copies .env.example to .env if missing
    6. Runs alembic upgrade head
    7. Starts ARQ worker (background)
    8. Starts uvicorn (background)
    9. Health-checks /health
   10. Prints URLs and a sample curl

  Run from the repo root:
    .\start-live.ps1

  To stop everything:
    .\stop-live.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipInstall = $false,
    [switch]$SkipMigrate = $false,
    [int]$ApiPort = 8000,
    [int]$WaitSeconds = 60
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step($msg)  { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "   [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "   [FAIL] $msg" -ForegroundColor Red }

$RepoRoot      = (Get-Location).Path
$VenvDir       = Join-Path $RepoRoot '.venv'
$EnvFile       = Join-Path $RepoRoot '.env'
$EnvExample    = Join-Path $RepoRoot '.env.example'
$LogDir        = Join-Path $RepoRoot '.runtime-logs'
$PidFile       = Join-Path $RepoRoot '.runtime-pids.json'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- 1. Pre-flight ---
Write-Step "Pre-flight checks"

try {
    $null = docker version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "docker not responding" }
    Write-Ok "Docker is available"
} catch {
    Write-Err "Docker is not installed or not running."
    Write-Host "         Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

try {
    $null = docker compose version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "compose v2 not found" }
    Write-Ok "docker compose v2 is available"
} catch {
    Write-Err "docker compose v2 not found. Update Docker Desktop."
    exit 1
}

$py = $null
foreach ($v in '3.14','3.13','3.12','3.11') {
    try {
        $out = & py -${v} --version 2>&1
        if ($LASTEXITCODE -eq 0) { $py = "py -${v}"; break }
    } catch {}
}
if (-not $py) {
    Write-Err "Python 3.11+ not found. Install from https://www.python.org/"
    exit 1
}
Write-Ok "Python found: $py"

# --- 2. Start Postgres + Redis ---
Write-Step "Starting Postgres + Redis via docker compose"
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) { Write-Err "docker compose up failed"; exit 1 }
Write-Ok "Containers requested"

# --- 3. Wait for health ---
Write-Step "Waiting for Postgres + Redis to be healthy (up to ${WaitSeconds}s)"

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$pgReady = $false
$redisReady = $false

while ((Get-Date) -lt $deadline) {
    if (-not $pgReady) {
        try {
            docker exec ab6-ai-vscode-postgres-1 pg_isready -U ab6 -d ab6_ai 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $pgReady = $true; Write-Ok "Postgres is ready" }
        } catch { }
    }
    if (-not $redisReady) {
        try {
            docker exec ab6-ai-vscode-redis-1 redis-cli ping 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $redisReady = $true; Write-Ok "Redis is ready" }
        } catch { }
    }
    if ($pgReady -and $redisReady) { break }
    Start-Sleep -Seconds 2
}

if (-not $pgReady) { Write-Err "Postgres not ready after ${WaitSeconds}s"; exit 1 }
if (-not $redisReady) { Write-Err "Redis not ready after ${WaitSeconds}s"; exit 1 }

# --- 4. Python venv + deps ---
if (-not (Test-Path $VenvDir)) {
    Write-Step "Creating Python venv at .venv"
    & py -3.11 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Err "venv creation failed"; exit 1 }
    Write-Ok "venv created"
} else {
    Write-Ok "venv already exists"
}

$venvPy  = Join-Path $VenvDir 'Scripts\python.exe'
$venvPip = Join-Path $VenvDir 'Scripts\pip.exe'

if (-not $SkipInstall) {
    Write-Step "Installing Python dependencies (this may take a minute)"
    & $venvPip install --upgrade pip --quiet
    & $venvPip install -e ".[dev]" --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed"; exit 1 }
    Write-Ok "Dependencies installed"
} else {
    Write-Ok "Skipping pip install (-SkipInstall)"
}

# --- 5. .env setup ---
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Warn ".env created from .env.example. EDIT IT and add at least one LLM API key!"
    } else {
        Write-Err ".env.example not found"; exit 1
    }
} else {
    Write-Ok ".env exists"
}

# Warn if no LLM key
$envBytes = [System.IO.File]::ReadAllBytes($EnvFile)
$envContent = [System.Text.Encoding]::UTF8.GetString($envBytes)
$hasKey = $false
foreach ($k in 'OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY') {
    if ($envContent -match "(?m)^${k}=.+" -and $envContent -notmatch "(?m)^${k}=\s*$" -and $envContent -notmatch "(?m)^${k}=sk-\.\.\.") {
        $hasKey = $true; break
    }
}
if (-not $hasKey) {
    Write-Warn "No LLM API key set in .env - agent will run in DEMO MODE (canned responses)"
    Write-Host "         Edit .env and add OPENAI_API_KEY=sk-... then re-run." -ForegroundColor Yellow
} else {
    Write-Ok "LLM API key detected"
}

# --- 6. Alembic migrations ---
if (-not $SkipMigrate) {
    Write-Step "Running database migrations (alembic upgrade head)"
    Push-Location $RepoRoot
    try {
        & $venvPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Warn "alembic exited non-zero (may be benign on first run)" }
        else { Write-Ok "Migrations applied" }
    } finally { Pop-Location }
} else {
    Write-Ok "Skipping migrations (-SkipMigrate)"
}

# --- 7. ARQ worker (background) ---
Write-Step "Starting ARQ worker (background)"

Get-Process -Name 'arq' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$arqLog = Join-Path $LogDir 'arq.log'
$arqProc = Start-Process -FilePath $venvPy `
    -ArgumentList '-m','arq','legacy.ingestion.worker.WorkerSettings' `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $arqLog `
    -RedirectStandardError (Join-Path $LogDir 'arq.err.log') `
    -PassThru -WindowStyle Hidden
Write-Ok "ARQ worker started (PID $($arqProc.Id), log: $arqLog)"

# --- 8. Uvicorn API (background) ---
Write-Step "Starting FastAPI / uvicorn (background) — mentor_app"

Get-Process -Name 'uvicorn' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$apiLog = Join-Path $LogDir 'api.log'
$apiProc = Start-Process -FilePath $venvPy `
    -ArgumentList '-m','uvicorn','mentor_app:app','--host','0.0.0.0','--port',$ApiPort,'--no-access-log' `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $apiLog `
    -RedirectStandardError (Join-Path $LogDir 'api.err.log') `
    -PassThru -WindowStyle Hidden
Write-Ok "Mentor started (PID $($apiProc.Id), log: $apiLog)"

# --- 9. Health check ---
Write-Step "Health-checking http://127.0.0.1:${ApiPort}/health"

$healthy = $false
for ($i = 1; $i -le 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:${ApiPort}/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}

if ($healthy) {
    Write-Ok "API is healthy"
} else {
    Write-Warn "API did not respond on /health within 20s. Check $LogDir\api.err.log"
}

# --- 10. Save PIDs + summary ---
$pidInfo = @{
    api   = @{ pid = $apiProc.Id; log = $apiLog }
    arq   = @{ pid = $arqProc.Id; log = $arqLog }
    ports = @{ api = $ApiPort }
} | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($PidFile, $pidInfo, [System.Text.UTF8Encoding]::new($false))

# --- Summary ---
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  AB6 AI AGENT - LIVE STACK UP" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API:       http://127.0.0.1:${ApiPort}" -ForegroundColor White
Write-Host "  Docs:      http://127.0.0.1:${ApiPort}/docs" -ForegroundColor White
Write-Host "  WebSocket: ws://127.0.0.1:${ApiPort}/api/v1/ai/telemetry/ws" -ForegroundColor White
Write-Host "  Postgres:  localhost:5432  (ab6 / ab6_pass / ab6_ai)" -ForegroundColor White
Write-Host "  Redis:     localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "  Logs:      $LogDir" -ForegroundColor White
Write-Host "  PIDs:      $PidFile" -ForegroundColor White
Write-Host ""
Write-Host "  --- Try it ---" -ForegroundColor Cyan
Write-Host "  curl -X POST http://127.0.0.1:8000/api/v1/ai/events ^"
Write-Host "       -H \"Content-Type: application/json\" ^"
Write-Host "       -d '{\"user_id\":\"u1\",\"session_id\":\"s1\",\"event_type\":\"end_attempt\",\"challenge_id\":\"ik-1\",\"score\":0.3,\"is_correct\":false}'"
Write-Host ""
Write-Host "  --- Stop everything ---" -ForegroundColor Cyan
Write-Host '  .\stop-live.ps1'
Write-Host ""
