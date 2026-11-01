"""Inject freshly researched Ahmedabad/Gandhinagar public emails + blast pitches."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.blacklist import ensure_schema, is_dead, remaining_quota
from agents.mass_brand_hunter import send_mass_queue, upsert_mass_brand, queue_hard_pitch
from app.database import get_conn, init_db
from app.services.emails import sender_profile

# Public emails found via live web research (Mar 2026)
BATCH = [
    ("FT Nexavvy", "hello@ftnexavvy.com", "Ahmedabad", "Digital marketing"),
    ("FT Nexavvy Founder", "founder@ftnexavvy.com", "Ahmedabad", "Digital marketing"),
    ("Nyasa", "hello@nyasa.co.in", "Ahmedabad", "Digital marketing"),
    ("Sunbots Innovations", "hello@sunbots.in", "Ahmedabad", "Marketing SaaS"),
    ("Conversifyit", "info@conversifyit.in", "Ahmedabad", "Digital marketing"),
    ("YehLo", "info@theyehlo.com", "Ahmedabad", "Branding"),
    ("Satva Marketing", "info@satvamarketing.com", "Gandhinagar", "Marketing"),
    ("Pixielit", "info@pixielit.com", "Gandhinagar", "Branding"),
    ("Advereal", "info@advereal.in", "Gandhinagar", "Manufacturing branding"),
    ("JRJ Foods", "info@jrjfoods.com", "Gandhinagar", "FMCG food"),
    ("Bhavana Add Agency", "bhavana1add@gmail.com", "Gandhinagar", "Advertising"),
]


def main():
    init_db()
    ensure_schema()
    sender = sender_profile()
    added = queued = 0
    with get_conn() as conn:
        for name, email, city, cat in BATCH:
            if is_dead(email):
                continue
            if upsert_mass_brand(conn, name, email, city, cat, "", "web_research"):
                added += 1
            row = conn.execute("SELECT id FROM brands WHERE lower(contact_email)=?", (email.lower(),)).fetchone()
            if row and queue_hard_pitch(
                conn, row["id"], {"name": name, "contact_email": email, "category": cat}, sender
            ):
                queued += 1
        # Also re-queue any mass_gujarat with email not yet pitched
        rows = conn.execute(
            """
            SELECT * FROM brands
            WHERE segment IN ('mass_gujarat','blithchron27','blithchron27_local')
              AND trim(ifnull(contact_email,''))!=''
            """
        ).fetchall()
        for r in rows:
            b = dict(r)
            if is_dead(b["contact_email"]):
                continue
            if queue_hard_pitch(conn, b["id"], b, sender):
                queued += 1
        total = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        mass = conn.execute("SELECT COUNT(*) FROM brands WHERE segment='mass_gujarat'").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM outreach WHERE status IN ('draft','approved') AND trim(ifnull(to_email,''))!=''"
        ).fetchone()[0]
    print("added", added, "queued", queued, "brands", total, "mass", mass, "pending", pending, "quota", remaining_quota(400))
    result = send_mass_queue(max_sends=min(120, remaining_quota(400) or 1), delay=0.45, daily_cap=400)
    print("SEND", result.get("sent"), "left", result.get("remaining_quota"), "errs", len(result.get("errors") or []))


if __name__ == "__main__":
    main()
