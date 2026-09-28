# ai: claude-sonnet-5 | 2026-07-20
<#
.SYNOPSIS
    Launches the CostcoPrices app.
.PARAMETER Dev
    Run in development mode: Vite dev server + uvicorn with hot-reload,
    instead of the default build-and-serve production mode.
.EXAMPLE
    .\launch.ps1
.EXAMPLE
    .\launch.ps1 -Dev
#>
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$mainScript = Join-Path $root "main.py"
if (-not (Test-Path $mainScript)) {
    Write-Error "[launch] main.py not found at $mainScript"
    exit 1
}

$backendPython = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    Write-Host "[launch] backend\.venv not found - falling back to 'py'/'python' on PATH." -ForegroundColor Yellow
    Write-Host "[launch] Run 'cd backend; uv sync' to create the backend virtual environment." -ForegroundColor Yellow

    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $pythonCmd) {
        Write-Error "[launch] No Python interpreter found on PATH."
        exit 1
    }
    $backendPython = $pythonCmd.Source
}

$scriptArgs = @($mainScript)
if ($Dev) {
    $scriptArgs += "--dev"
}

& $backendPython @scriptArgs
exit $LASTEXITCODE
