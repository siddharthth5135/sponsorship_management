"""
Run the full agent team once.

Usage:
  python -m agents.orchestrator --daily
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.discovery import run_discovery  # noqa: E402
from app.database import get_conn, init_db  # noqa: E402
from app.services.emails import brand_email, organizer_email, sender_profile  # noqa: E402
from app.services.matching import score_match  # noqa: E402
from app.services.opportunity import rescore_all_events  # noqa: E402

MATCH_THRESHOLD = 50


def log_run(agent_name: str, run_type: str, summary: str, items: int, actions: list[dict]):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (agent_name, run_type, summary, items_created, founder_actions_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_name, run_type, summary, items, json.dumps(actions)),
        )


def add_founder_task(
    title: str,
    description: str,
    priority: str,
    agent: str,
    related_type: str = "",
    related_id: int | None = None,
    conn=None,
) -> bool:
    """Create a task unless an identical pending one already exists."""

    def _insert(c) -> bool:
        exists = c.execute(
            "SELECT 1 FROM founder_tasks WHERE title=? AND status='pending'", (title,)
        ).fetchone()
        if exists:
            return False
        c.execute(
            """
            INSERT INTO founder_tasks (title, description, priority, related_type, related_id, created_by_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, priority, related_type or None, related_id, agent),
        )
        return True

    if conn is not None:
        return _insert(conn)
    with get_conn() as c:
        return _insert(c)


def agent_event_scout(include_discovery: bool = True) -> int:
    """Grow the event book, score for real sponsorship chance, then queue chase tasks only."""
    discovery_stats = (
        run_discovery()
        if include_discovery
        else {"events_added": 0, "college_seeded": 0, "allevents_added": 0, "candidates": 0}
    )
    count = 0
    with get_conn() as conn:
        tiers = rescore_all_events(conn)
        # Clean drafts/matches for inventory we will not chase
        for row in conn.execute("SELECT id FROM events WHERE opportunity_tier='skip'").fetchall():
            conn.execute(
                "DELETE FROM outreach WHERE target_type='event' AND target_id=? AND status='draft'",
                (row["id"],),
            )
            conn.execute("DELETE FROM matches WHERE event_id=? AND status='suggested'", (row["id"],))
        chase_n = tiers.get("chase", 0)
        research_n = tiers.get("research", 0)
        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE loi_signed=0
              AND opportunity_tier='chase'
              AND planning_stage IN ('planning','seeking_sponsors','packages_open')
            ORDER BY opportunity_score DESC, id DESC
            """
        ).fetchall()
        for row in rows:
            e = dict(row)
            contact = e.get("organizer_email") or e.get("organizer_phone") or "contact via website/LinkedIn"
            why = e.get("opportunity_reason") or "High sponsorship opportunity."
            desc = (
                f"{why} Contact: {contact}. "
                "Goal: get their sponsor deck and agreement that you sell open slots for a 10–15% success fee."
            )
            if add_founder_task(
                f"Win the organizer: {e['name']}", desc, "high", "event_scout", "event", e["id"], conn=conn
            ):
                count += 1
    added = discovery_stats.get("events_added", 0)
    log_run(
        "Event Scout",
        "daily",
        (
            f"Smart filter: {chase_n} chase / {research_n} research / {tiers.get('skip', 0)} skipped. "
            f"Added {added} after opportunity gate. Queued {count} chase follow-ups "
            "(no celebrity tours / directories)."
        ),
        count + added,
        [],
    )
    return count + added


def agent_brand_scout() -> int:
    count = 0
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM brands").fetchall()
        for row in rows:
            b = dict(row)
            if b.get("contact_email") and b.get("contact_name"):
                continue
            desc = (
                f"{b['name']} only has a general inbox ({b.get('contact_email') or 'none'}). "
                "Find the marketing / brand manager on LinkedIn and add their name and email to the brand."
            )
            if add_founder_task(f"Find marketing contact: {b['name']}", desc, "medium", "brand_scout", "brand", b["id"], conn=conn):
                count += 1
    log_run("Brand Scout", "daily", f"{count} new contact-research tasks.", count, [])
    return count


def agent_fit_matcher() -> int:
    upserted = 0
    with get_conn() as conn:
        events = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM events WHERE ifnull(opportunity_tier,'chase') IN ('chase','research')"
            ).fetchall()
        ]
        brands = [dict(r) for r in conn.execute("SELECT * FROM brands").fetchall()]
        for event in events:
            for brand in brands:
                score, tier, reason = score_match(event, brand)
                if score < MATCH_THRESHOLD:
                    conn.execute(
                        "DELETE FROM matches WHERE event_id=? AND brand_id=? AND status='suggested'",
                        (event["id"], brand["id"]),
                    )
                    continue
                conn.execute(
                    """
                    INSERT INTO matches (event_id, brand_id, fit_score, fit_tier, status, match_reason)
                    VALUES (?, ?, ?, ?, 'suggested', ?)
                    ON CONFLICT(event_id, brand_id) DO UPDATE SET
                        fit_score=excluded.fit_score,
                        fit_tier=excluded.fit_tier,
                        match_reason=excluded.match_reason,
                        updated_at=datetime('now')
                    """,
                    (event["id"], brand["id"], score, tier, reason),
                )
                upserted += 1
    log_run("Fit Matcher", "daily", f"{upserted} brand–event matches scored (≥{MATCH_THRESHOLD}%).", upserted, [])
    return upserted


def _upsert_draft(conn, target_type: str, target_id: int, to_name: str, to_email: str, subject: str, body: str, sender: dict) -> bool:
    existing = conn.execute(
        "SELECT id, status FROM outreach WHERE target_type=? AND target_id=? ORDER BY id DESC LIMIT 1",
        (target_type, target_id),
    ).fetchone()
    if existing and existing["status"] != "draft":
        return False
    if existing:
        conn.execute(
            "UPDATE outreach SET subject=?, body=?, to_name=?, to_email=?, from_email=? WHERE id=?",
            (subject, body, to_name, to_email, sender["email"], existing["id"]),
        )
        return False
    conn.execute(
        """
        INSERT INTO outreach (target_type, target_id, channel, subject, body, status, agent_name,
            to_name, to_email, from_email)
        VALUES (?, ?, 'email', ?, ?, 'draft', 'outreach_writer', ?, ?, ?)
        """,
        (target_type, target_id, subject, body, to_name, to_email, sender["email"]),
    )
    return True


def agent_outreach_writer() -> int:
    sender = sender_profile()
    created = 0
    with get_conn() as conn:
        for row in conn.execute(
            """
            SELECT * FROM events
            WHERE loi_signed=0 AND opportunity_tier='chase'
            ORDER BY opportunity_score DESC
            """
        ).fetchall():
            e = dict(row)
            subject, body = organizer_email(e, sender)
            to_name = e.get("organizer_name") or f"{e['name']} team"
            if _upsert_draft(conn, "event", e["id"], to_name, e.get("organizer_email") or "", subject, body, sender):
                created += 1

        rows = conn.execute(
            """
            SELECT m.brand_id, m.fit_score, e.*
            FROM matches m JOIN events e ON e.id = m.event_id
            WHERE ifnull(e.opportunity_tier,'chase') IN ('chase','research')
            ORDER BY m.fit_score DESC
            """
        ).fetchall()
        by_brand: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            by_brand[r["brand_id"]].append(dict(r))
        for brand_id, events in by_brand.items():
            b = dict(conn.execute("SELECT * FROM brands WHERE id=?", (brand_id,)).fetchone())
            subject, body = brand_email(b, events, sender)
            to_name = b.get("contact_name") or f"{b['name']} marketing"
            if _upsert_draft(conn, "brand", brand_id, to_name, b.get("contact_email") or "", subject, body, sender):
                created += 1
    log_run("Outreach Writer", "daily", f"{created} new drafts (existing drafts refreshed).", created, [])
    return created


def agent_pipeline_chief() -> int:
    with get_conn() as conn:
        drafts = conn.execute("SELECT COUNT(*) FROM outreach WHERE status='draft'").fetchone()[0]
        matches = conn.execute("SELECT COUNT(*) FROM matches WHERE status='suggested'").fetchone()[0]
        deals = conn.execute("SELECT COUNT(*) FROM deals WHERE status NOT IN ('closed','lost')").fetchone()[0]
        today = conn.execute("SELECT date('now')").fetchone()[0]
    summary = f"{drafts} emails ready to send, {matches} matches to review, {deals} open deals."
    add_founder_task(
        f"Daily plan — {today}",
        summary + " Send 3 organizer emails and 2 brand emails today, then log replies.",
        "high",
        "pipeline_chief",
    )
    log_run("Pipeline Chief", "daily", summary, 1, [])
    return 1


def agent_deal_desk() -> int:
    count = 0
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM deals WHERE payment_received=0 AND status='agreed'").fetchall()
        for row in rows:
            d = dict(row)
            desc = f"Deal ₹{d['deal_amount']:,} — your commission ₹{d['commission_amount']:,} ({d['commission_pct']}%)."
            if add_founder_task(f"Collect payment: deal #{d['id']}", desc, "high", "deal_desk", "deal", d["id"], conn=conn):
                count += 1
    log_run("Deal Desk", "daily", f"{count} payment reminders.", count, [])
    return count


def run_daily(include_discovery: bool = True) -> dict:
    init_db()
    results: dict = {
        "event_scout": agent_event_scout(include_discovery=include_discovery),
        "brand_scout": agent_brand_scout(),
        "fit_matcher": agent_fit_matcher(),
        "outreach_writer": agent_outreach_writer(),
        "pipeline_chief": agent_pipeline_chief(),
        "deal_desk": agent_deal_desk(),
    }
    print("Agent team run complete:")
    print(json.dumps(results, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily", action="store_true", help="Run the full agent team once")
    parser.add_argument("--no-discovery", action="store_true", help="Skip the web scan")
    args = parser.parse_args()
    if args.daily:
        run_daily(include_discovery=not args.no_discovery)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
