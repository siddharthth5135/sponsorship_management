Set-Location $PSScriptRoot\..
.\.venv\Scripts\Activate.ps1
python -m agents.orchestrator --daily
Write-Host "Open http://127.0.0.1:8000 after starting: python -m uvicorn app.main:app --reload"
