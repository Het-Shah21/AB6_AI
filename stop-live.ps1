<#
.SYNOPSIS
  Stops the AB6 live stack started by start-live.ps1
#>

[CmdletBinding()]
param(
    [switch]$AlsoDocker = $false   # also stop the postgres+redis containers
)

$ErrorActionPreference = 'SilentlyContinue'
$RepoRoot = (Get-Location).Path
$PidFile = Join-Path $RepoRoot '.runtime-pids.json'

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }

Write-Step "Stopping AB6 live stack"

# Stop via PIDs from .runtime-pids.json
if (Test-Path $PidFile) {
    $pids = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($proc in @('api','arq','ui')) {
        $id = $pids.$proc.pid
        if ($id) {
            $p = Get-Process -Id $id -ErrorAction SilentlyContinue
            if ($p) {
                Stop-Process -Id $id -Force
                Write-Ok "Stopped $proc (PID $id)"
            } else {
                Write-Host "   $proc (PID $id) was not running" -ForegroundColor DarkGray
            }
        }
    }
} else {
    Write-Host "   No .runtime-pids.json found — falling back to name-based kill" -ForegroundColor Yellow
}

# Belt and suspenders: also kill by name
Get-Process -Name 'uvicorn' -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Ok "Killed uvicorn PID $($_.Id)"
}
Get-Process -Name 'arq' -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Ok "Killed arq PID $($_.Id)"
}
Get-Process -Name 'streamlit' -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Ok "Killed streamlit PID $($_.Id)"
}

if ($AlsoDocker) {
    Write-Step "Stopping Docker containers (postgres + redis)"
    docker compose stop postgres redis
    if ($LASTEXITCODE -eq 0) { Write-Ok "Containers stopped (use 'docker compose down' to remove)" }
} else {
    Write-Host "   (Postgres + Redis containers left running. Use -AlsoDocker to stop them.)" -ForegroundColor DarkGray
}

if (Test-Path $PidFile) { Remove-Item $PidFile }
Write-Host "`nDone.`n" -ForegroundColor Green
