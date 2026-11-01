# Sponsorship Brokerage OS

Private internal system for your sponsorship brokerage (not a public marketplace).

## Quick start

```powershell
cd "c:\Users\SIDDHARTH\OneDrive\Desktop\NEWLY REGISTERED BUSINESSES\sponsorship-brokerage-os"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m agents.orchestrator --seed-demo
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**

## Daily workflow

1. Run agents: `python -m agents.orchestrator --daily`
2. Open **Dashboard → Your tasks**
3. Approve outreach drafts → send from your email
4. Call organizers (LOI) and brands (intros)
5. Record closed deals under **Deals**

## Agent team (6)

See `agents/team.json` and `docs/END_TO_END_OVERVIEW.md`.

## Docs (manual)

- Project: `docs/OPERATIONS_MANUAL.html` (print to PDF)
- Root copy: `../SPONSORSHIP_BROKERAGE_OPERATIONS_MANUAL.html`
- Demo: open `demo/walkthrough.html` in browser (screen-record for video)

## Tests

```powershell
pytest tests/test_e2e.py -v
```
