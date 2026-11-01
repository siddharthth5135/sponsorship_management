Set-Location $PSScriptRoot\..
.\.venv\Scripts\Activate.ps1
Write-Host "Starting SponsorDesk agent daemon (discovery + team every ~45 min)..."
python -m agents.daemon
