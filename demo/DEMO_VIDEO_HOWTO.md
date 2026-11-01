# How to record your demo video (5 minutes)

1. Start the app:
   ```powershell
   cd sponsorship-brokerage-os
   .\.venv\Scripts\Activate.ps1
   python -m agents.orchestrator --seed-demo
   python -m uvicorn app.main:app --reload
   ```
2. Press **Win + G** (Xbox Game Bar) → Record.
3. Walk through:
   - Dashboard (your task count)
   - Your tasks → mark one done
   - Outreach → Approve draft
   - Matches → Run matcher / approve
   - Deals → show commission
4. Optional: open `demo/walkthrough.html` first for intro slides.
5. Save video as `demo/brokerage-os-demo.mp4` in this folder.

AI cannot record your screen with audio in this environment; this 5-minute recording is the official demo for investors/teammates.
