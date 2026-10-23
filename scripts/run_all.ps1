# Starts DeleteMe agents on Windows with logs going to logs/

$ErrorActionPreference = "Stop"

if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

$PYTHON = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "Starting DeleteMe Agents..." -ForegroundColor Cyan

# Start Concierge
$conciergeProc = Start-Process -FilePath $PYTHON -ArgumentList "-m agents.concierge.agent" -RedirectStandardOutput "logs\concierge.log" -RedirectStandardError "logs\concierge.err.log" -PassThru
Write-Host "[+] Concierge Agent started (PID: $($conciergeProc.Id)) -> logs\concierge.log" -ForegroundColor Green

Write-Host "Agents running. Check logs in .\logs\" -ForegroundColor Yellow
