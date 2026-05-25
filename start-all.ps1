#requires -Version 5.1
<#
.SYNOPSIS
  llm-nexus 의 Postgres + 백엔드 + 프런트엔드를 한꺼번에 띄운다.

.DESCRIPTION
  - Postgres: docker compose up -d postgres
  - Backend:  uvicorn (별도 윈도우)
  - Frontend: next dev (별도 윈도우)
  - llama-server 는 GPU 를 점유하므로 별도로 직접 띄워야 함.

  실행 후 각 헬스체크 엔드포인트로 기동 확인. Ctrl+C 한 번으로 모두 종료되진 않음 —
  열린 PowerShell 창을 각각 닫거나 docker compose down 으로 정리.

.PARAMETER NoFrontend
  프런트엔드는 띄우지 않는다.

.PARAMETER NoBackend
  백엔드는 띄우지 않는다.

.EXAMPLE
  .\start-all.ps1
  .\start-all.ps1 -NoFrontend
#>

param(
    [switch]$NoBackend,
    [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "[1/3] Postgres (docker compose)..." -ForegroundColor Cyan
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose 실패. Docker Desktop 이 떠 있는지 확인."
    exit 1
}

if (-not $NoBackend) {
    Write-Host "[2/3] FastAPI 백엔드 (새 창)..." -ForegroundColor Cyan
    $venvUvicorn = Join-Path $root ".venv\Scripts\uvicorn.exe"
    $venvAlembic = Join-Path $root ".venv\Scripts\alembic.exe"
    if (-not (Test-Path $venvUvicorn)) {
        Write-Error ".venv\Scripts\uvicorn.exe 가 없음. .\.venv\Scripts\pip install -r backend\requirements.txt 먼저 실행."
        exit 1
    }
    # 백엔드 기동 전 마이그레이션 적용 (lifespan 자동화 대신 명시적).
    Write-Host "  → alembic upgrade head" -ForegroundColor DarkCyan
    Push-Location (Join-Path $root "backend")
    & $venvAlembic upgrade head
    Pop-Location
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$root'; & '$venvUvicorn' backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
    )
} else {
    Write-Host "[2/3] 백엔드 스킵 (-NoBackend)" -ForegroundColor DarkGray
}

if (-not $NoFrontend) {
    Write-Host "[3/3] Next.js 프런트엔드 (새 창)..." -ForegroundColor Cyan
    $frontendDir = Join-Path $root "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Warning "frontend\node_modules 없음. 먼저 'cd frontend; npm install' 실행 필요."
    }
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$frontendDir'; npm run dev"
    )
} else {
    Write-Host "[3/3] 프런트엔드 스킵 (-NoFrontend)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "기동 완료. llama-server 는 별도로 띄워야 함:" -ForegroundColor Yellow
Write-Host "  .\llama-server.exe -m <model.gguf> -ngl 99 -c 8192 --flash-attn on --port 11434" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "헬스체크:" -ForegroundColor Yellow
Write-Host "  curl http://localhost:8000/health"
Write-Host "  curl http://localhost:8000/health/llm"
Write-Host "  curl http://localhost:8000/health/db"
Write-Host ""
Write-Host "프런트엔드: http://localhost:3000" -ForegroundColor Yellow
