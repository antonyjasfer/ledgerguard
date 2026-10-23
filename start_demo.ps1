# LedgerGuard Alexa+ Multi-Modal CFO & Argon2 Vault Launcher
# Amazon Developer Hackathon (Alexa+ Track + AWS Builder + Open Source)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " LEDGERGUARD - ALEXA+ ACCOUNTS PAYABLE CFO & ARGON2 CRYPTOGRAPHIC VAULT" -ForegroundColor Cyan
Write-Host " Amazon Developer Hackathon 2026: Alexa+ Track + AWS Builder + OSS Mini-Challenge" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. Enforce AWS CLI profile and region
$env:AWS_PROFILE = "ledgerguard"
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:AWS_REGION = "us-east-1"

Write-Host "`n[1/3] AWS Configuration set:" -ForegroundColor Yellow
Write-Host "      Profile: $env:AWS_PROFILE" -ForegroundColor Gray
Write-Host "      Region:  $env:AWS_DEFAULT_REGION" -ForegroundColor Gray

# 2. Activate virtual environment
Write-Host "`n[2/3] Activating Python 3.11 virtual environment (.venv)..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# 3. Display live endpoints
Write-Host "`n[3/3] Launching FastAPI + Uvicorn server..." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor DarkGray
Write-Host "  INTERACTIVE ALEXA+ SIMULATOR : http://127.0.0.1:8000/alexa" -ForegroundColor White -BackgroundColor DarkGreen
Write-Host "  ALEXA+ MCP STREAMABLE HTTP   : http://127.0.0.1:8000/mcp"   -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "  SWAGGER / OPENAPI API DOCS   : http://127.0.0.1:8000/docs"  -ForegroundColor DarkCyan
Write-Host "================================================================================" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop the demo server.`n" -ForegroundColor DarkGray

& ".\.venv\Scripts\python.exe" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
