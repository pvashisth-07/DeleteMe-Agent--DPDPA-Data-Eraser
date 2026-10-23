# DeleteMe Agent: Full Scenario Demonstration (PowerShell)
# Canonical Swiggy / Zomato / Paytm flow with Demo Clock

$env:SEND_MODE = "demo_redirect"
$env:DEMO_CLOCK_SPEED = "86400"
$env:PAYMENTS_BYPASS_FOR_DEMO = "true"
$env:DEBUG_MODE = "true"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting DeleteMe Full Scenario Demo (DPDPA 2023 Agent)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

.venv\Scripts\python.exe scripts/demo.py
