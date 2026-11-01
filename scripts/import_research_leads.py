"""One-time import of verified public sponsorship calls (Gujarat / nearby)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.discovery import migrate  # noqa: E402
from app.database import get_conn, init_db  # noqa: E402

LEADS = [
    {
        "type": "event",
        "name": "CHAOS'26 — IIM Ahmedabad Cultural Fest",
        "city": "Ahmedabad, Gujarat",
        "category": "Education / College fest",
        "stage": "seeking_sponsors",
        "footfall": 100000,
        "organizer_email": "chaos-corpcomm@iima.ac.in",
        "source": "https://www.linkedin.com/posts/chaos-iima_chaos26-iima-partnerships-activity-7394964749500915712-tbRq",
        "why": "Public call for brand partnerships; 100k+ footfall; Jan 16–18 2026.",
        "notes": "Title/co-title slots mentioned for FMCG, finance, lifestyle brands.",
    },
    {
        "type": "event",
        "name": "Tesseract XI — PDEU Gandhinagar",
        "city": "Gandhinagar, Gujarat",
        "category": "Technology",
        "stage": "seeking_sponsors",
        "footfall": 5000,
        "organizer_email": "tesseractpdeu@gmail.com",
        "organizer_phone": "+91 9408952863",
        "source": "https://www.linkedin.com/posts/science-technical-committee-of-pdeu_tesseractxi-pdeu-snt-activity-7374766748660822017-QPR5",
        "why": "Explicit call for sponsors; technical fest with multi-club footprint.",
        "notes": "Contacts: Aditya Mehta, Saurav Kaushik on LinkedIn post.",
    },
    {
        "type": "event",
        "name": "WordPress Campus Connect — Adani University Ahmedabad",
        "city": "Ahmedabad, Gujarat",
        "category": "Education",
        "stage": "packages_open",
        "footfall": 80,
        "organizer_email": "",
        "source": "https://events.wordpress.org/campusconnect/2026/adani-university-ahmedabad/call-for-sponsors/",
        "why": "Published sponsor tiers (Gold ₹30k / Silver ₹20k) — easy package match.",
        "notes": "Good first small deal for local tech/D2C brands.",
    },
]


def main():
    init_db()
    migrate()
    added = 0
    with get_conn() as conn:
        for L in LEADS:
            url = L["source"]
            if conn.execute("SELECT COUNT(*) FROM discoveries WHERE source_url=?", (url,)).fetchone()[0]:
                continue
            why = L["why"]
            conn.execute(
                """
                INSERT INTO events (name, city, category, planning_stage, footfall_estimate,
                    organizer_email, organizer_phone, notes, source_url, discovery_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    L["name"],
                    L["city"],
                    L["category"],
                    L["stage"],
                    L.get("footfall", 0),
                    L.get("organizer_email", ""),
                    L.get("organizer_phone", ""),
                    L["notes"],
                    url,
                    why,
                ),
            )
            eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO discoveries (lead_type, title, snippet, source_url, query_used, why_chosen, status, imported_table, imported_id)
                VALUES ('event', ?, ?, ?, 'research_import', ?, 'imported', 'events', ?)
                """,
                (L["name"], L["notes"], url, why, eid),
            )
            added += 1
    print(f"Imported {added} researched event leads.")


if __name__ == "__main__":
    main()
