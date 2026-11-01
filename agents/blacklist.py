"""Dead-email blacklist — bounced addresses are NEVER retried."""

from __future__ import annotations

from app.database import get_conn, init_db


def ensure_schema() -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dead_emails (
                email TEXT PRIMARY KEY,
                reason TEXT DEFAULT 'bounced',
                brand_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lead_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_name TEXT NOT NULL,
                from_email TEXT DEFAULT '',
                snippet TEXT DEFAULT '',
                outreach_id INTEGER,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS send_quota (
                day TEXT PRIMARY KEY,
                sent_count INTEGER DEFAULT 0
            )
            """
        )


def mark_dead(email: str, reason: str = "bounced", brand_id: int | None = None) -> None:
    ensure_schema()
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        return
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO dead_emails (email, reason, brand_id) VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET reason=excluded.reason
            """,
            (e, (reason or "bounced")[:300], brand_id),
        )
        # Kill any pending drafts to this address
        conn.execute(
            """
            UPDATE outreach SET status='bounced',
              send_error=COALESCE(NULLIF(send_error,''), ?)
            WHERE lower(to_email)=? AND status IN ('draft','approved')
            """,
            (f"Blacklisted: {reason}"[:400], e),
        )


def is_dead(email: str) -> bool:
    ensure_schema()
    e = (email or "").strip().lower()
    if not e:
        return True
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM dead_emails WHERE email=?", (e,)).fetchone()
    return bool(row)


def sync_from_bounced_outreach() -> int:
    """Import all current bounced outreach emails into the blacklist."""
    ensure_schema()
    n = 0
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT lower(to_email) AS e, target_id
            FROM outreach
            WHERE status='bounced' AND trim(ifnull(to_email,'')) != ''
            """
        ).fetchall()
        for r in rows:
            conn.execute(
                """
                INSERT INTO dead_emails (email, reason, brand_id) VALUES (?, 'bounced', ?)
                ON CONFLICT(email) DO NOTHING
                """,
                (r["e"], r["target_id"]),
            )
            n += 1
    return n


def sent_today() -> int:
    ensure_schema()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT sent_count FROM send_quota WHERE day=date('now')"
        ).fetchone()
    return int(row["sent_count"]) if row else 0


def bump_sent(n: int = 1) -> int:
    ensure_schema()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO send_quota (day, sent_count) VALUES (date('now'), ?)
            ON CONFLICT(day) DO UPDATE SET sent_count=sent_count+excluded.sent_count
            """,
            (n,),
        )
        row = conn.execute(
            "SELECT sent_count FROM send_quota WHERE day=date('now')"
        ).fetchone()
    return int(row["sent_count"]) if row else n


def remaining_quota(daily_cap: int = 400) -> int:
    return max(0, int(daily_cap) - sent_today())
