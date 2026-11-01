"""Clear all demo/dummy CRM data for production go-live."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import clear_all_data  # noqa: E402

if __name__ == "__main__":
    clear_all_data()
    print("SponsorDesk is live with an empty database.")
    print("Add real events and brands in the app, then run agents.orchestrator --daily")
