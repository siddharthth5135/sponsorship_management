"""Print pipeline counts and every outreach draft (To / From / Subject / Body)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_conn  # noqa: E402

with get_conn() as c:
    for table in ("events", "brands", "matches", "outreach", "founder_tasks"):
        print(f"{table}: {c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
    only = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    for r in c.execute("SELECT * FROM outreach ORDER BY target_type DESC, id"):
        if only and only not in (r["to_email"] or "").lower():
            continue
        print("\n" + "=" * 70)
        print(f"FROM: {r['from_email']}\nTO:   {r['to_email'] or '(no public email)'} ({r['to_name']})")
        print(f"SUBJECT: {r['subject']}\n")
        print(r["body"])
