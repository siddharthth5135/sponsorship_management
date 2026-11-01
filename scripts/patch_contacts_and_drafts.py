"""Patch LinkedIn URLs on existing leads and refresh unsent outreach drafts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_conn, init_db  # noqa: E402
from agents.orchestrator import agent_outreach_writer  # noqa: E402
from scripts.load_verified_leads import BRANDS, EVENTS  # noqa: E402


def main():
    init_db()
    with get_conn() as conn:
        for e in EVENTS:
            conn.execute(
                """
                UPDATE events
                SET linkedin_url=?, website=?, contact_role=?, source_url=?
                WHERE name=?
                """,
                (
                    e.get("linkedin_url", ""),
                    e.get("website", ""),
                    e.get("contact_role", ""),
                    e.get("source_url", ""),
                    e["name"],
                ),
            )
        for b in BRANDS:
            conn.execute(
                """
                UPDATE brands
                SET linkedin_url=?, website=?, contact_role=?, source_url=?
                WHERE name=?
                """,
                (
                    b.get("linkedin_url", ""),
                    b.get("website", ""),
                    b.get("contact_role", ""),
                    b.get("source_url", ""),
                    b["name"],
                ),
            )
    n = agent_outreach_writer()
    print(f"Patched contacts. Refreshed drafts (new created: {n}).")


if __name__ == "__main__":
    main()
