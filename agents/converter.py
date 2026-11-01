"""
Conversion engine — pitches clients and sends messages without waiting for approval.

Primary goal: move prospects toward a call / yes. Scouting feeds this; it is not the main job.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from agents import activity
from agents.orchestrator import agent_outreach_writer, log_run
from app.database import get_conn
from app.services.bounces import check_bounces
from app.services.emails import (
    BLITHCHRON_BROCHURE_URL,
    blithchron_brand_email,
    blithchron_brochure_email,
    sender_profile,
)
from app.services.mailer import MailerError, gmail_ready, send_email
from app.services.messaging import pitch_text


def conversion_config(cfg: dict | None = None) -> dict:
    raw = (cfg or {}).get("conversion") or {}
    return {
        "auto_send": bool(raw.get("auto_send", True))
        and os.environ.get("AUTO_SEND", "1").strip().lower() not in ("0", "false", "off", "no"),
        "max_sends_per_cycle": max(1, int(raw.get("max_sends_per_cycle", 12))),
        "followup_days": max(2, int(raw.get("followup_days", 3))),
        "send_delay_seconds": float(raw.get("send_delay_seconds", 1.2)),
        "scout_every_n_cycles": max(1, int(raw.get("scout_every_n_cycles", 3))),
    }


def _refresh_blithchron_pitches() -> int:
    """Ensure Blithchron leads with email have a current pitch draft."""
    sender = sender_profile()
    refreshed = 0
    with get_conn() as conn:
        brands = conn.execute(
            """
            SELECT * FROM brands
            WHERE segment IN ('blithchron27','blithchron27_local')
              AND trim(ifnull(contact_email,'')) != ''
            ORDER BY conversion_tier DESC, id
            """
        ).fetchall()
        for row in brands:
            b = dict(row)
            agent = b.get("segment") or "blithchron27"
            existing = conn.execute(
                """
                SELECT id, status FROM outreach
                WHERE target_type='brand' AND target_id=? AND agent_name=?
                ORDER BY id DESC LIMIT 1
                """,
                (b["id"], agent),
            ).fetchone()
            if existing and existing["status"] == "sent":
                continue
            subject, body = blithchron_brand_email(b, sender)
            to_name = b.get("contact_name") or b["name"]
            to_email = (b.get("contact_email") or "").strip()
            if existing and existing["status"] in ("draft", "approved"):
                conn.execute(
                    """
                    UPDATE outreach SET subject=?, body=?, to_name=?, to_email=?, from_email=?,
                      founder_approved=1, status='approved'
                    WHERE id=?
                    """,
                    (subject, body, to_name, to_email, sender.get("email") or "", existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO outreach (
                        target_type, target_id, channel, subject, body, status, agent_name,
                        to_name, to_email, from_email, founder_approved
                    ) VALUES ('brand', ?, 'email', ?, ?, 'approved', ?, ?, ?, ?, 1)
                    """,
                    (b["id"], subject, body, agent, to_name, to_email, sender.get("email") or ""),
                )
            refreshed += 1
    return refreshed


def _queue_phone_pitches(limit: int = 20) -> int:
    """Log WhatsApp-ready pitches for phone-only leads (no email gateway)."""
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT * FROM brands
            WHERE segment IN ('blithchron27','blithchron27_local','hunter')
              AND trim(ifnull(contact_email,'')) = ''
              AND trim(ifnull(contact_phone,'')) != ''
            ORDER BY conversion_tier DESC, id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()]
    # Log AFTER DB connection closed — never nest get_conn
    for b in rows:
        text = pitch_text(b)
        activity.log(
            f"WhatsApp pitch ready: {b['name']}",
            level="info",
            agent="Closer",
            detail=f"Phone {b.get('contact_phone')} — open Blithchron page to 1-tap send. Preview: {text[:160]}…",
            meta={"brand_id": b["id"], "channel": "whatsapp", "phone": b.get("contact_phone")},
        )
    return len(rows)


def queue_brochure_to_everyone() -> int:
    """Create approved brochure-share drafts for every Blithchron email lead not yet sent the PDF."""
    sender = sender_profile()
    queued_names: list[str] = []
    with get_conn() as conn:
        brands = conn.execute(
            """
            SELECT * FROM brands
            WHERE segment IN ('blithchron27','blithchron27_local')
              AND trim(ifnull(contact_email,'')) != ''
            ORDER BY conversion_tier DESC, id
            """
        ).fetchall()
        for row in brands:
            b = dict(row)
            already = conn.execute(
                """
                SELECT id, status FROM outreach
                WHERE target_type='brand' AND target_id=? AND agent_name='brochure'
                ORDER BY id DESC LIMIT 1
                """,
                (b["id"],),
            ).fetchone()
            if already and already["status"] == "sent":
                continue
            # Skip if any sent mail to this brand already included the Drive file
            prior = conn.execute(
                """
                SELECT id FROM outreach
                WHERE target_type='brand' AND target_id=? AND status='sent'
                  AND body LIKE '%1krYH0O00IcL654k4cNzImwliUc2oGPKO%'
                LIMIT 1
                """,
                (b["id"],),
            ).fetchone()
            if prior:
                continue
            subject, body = blithchron_brochure_email(b, sender)
            to_name = b.get("contact_name") or b["name"]
            to_email = (b.get("contact_email") or "").strip()
            if already:
                conn.execute(
                    """
                    UPDATE outreach SET subject=?, body=?, to_name=?, to_email=?, from_email=?,
                      founder_approved=1, status='approved', send_error=''
                    WHERE id=?
                    """,
                    (subject, body, to_name, to_email, sender.get("email") or "", already["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO outreach (
                        target_type, target_id, channel, subject, body, status, agent_name,
                        to_name, to_email, from_email, founder_approved
                    ) VALUES ('brand', ?, 'email', ?, ?, 'approved', 'brochure', ?, ?, ?, 1)
                    """,
                    (b["id"], subject, body, to_name, to_email, sender.get("email") or ""),
                )
            queued_names.append(b["name"])
    activity.log(
        f"Brochure queued for {len(queued_names)} brand(s)",
        level="success",
        agent="Closer",
        detail=BLITHCHRON_BROCHURE_URL
        + ((" · " + ", ".join(queued_names[:12])) if queued_names else " · nothing new"),
    )
    return len(queued_names)


def prepare_pitches() -> dict:
    """Write / refresh conversion pitches. Marks email drafts approved for auto-send."""
    activity.log(
        "Writing conversion pitches + attaching official brochure link…",
        agent="Pitch Writer",
        step=True,
        meta={"phase": "pitching"},
    )
    brochure_n = queue_brochure_to_everyone()
    blith = _refresh_blithchron_pitches()
    general = agent_outreach_writer()
    # Mark unsent drafts with emails as approved so converter can fire them
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE outreach
            SET founder_approved=1,
                status=CASE WHEN status='draft' THEN 'approved' ELSE status END
            WHERE status IN ('draft','approved')
              AND trim(ifnull(to_email,'')) != ''
            """
        )
    wa = _queue_phone_pitches()
    activity.bump_finds(drafts=blith + general + brochure_n)
    activity.log(
        f"Pitches ready — {brochure_n} brochure shares, {blith} Blithchron, {general} general, {wa} WhatsApp-ready",
        level="success",
        agent="Pitch Writer",
        detail=f"Brochure: {BLITHCHRON_BROCHURE_URL}",
    )
    return {
        "brochure_queued": brochure_n,
        "blithchron_pitches": blith,
        "general_drafts": general,
        "whatsapp_ready": wa,
    }


def auto_send_pitches(max_sends: int = 12, delay: float = 1.2) -> dict:
    """Send approved/draft emails now — no founder click required."""
    if not gmail_ready():
        activity.log(
            "Cannot auto-send — add Gmail App Password on Outreach first",
            level="warn",
            agent="Closer",
            step=True,
            meta={"phase": "sending"},
            detail="Conversion is blocked until SMTP is configured.",
        )
        return {"sent": 0, "errors": ["gmail_not_ready"], "skipped": 0}

    activity.log(
        f"Auto-sending up to {max_sends} conversion emails (no approval wait)…",
        agent="Closer",
        step=True,
        meta={"phase": "sending"},
    )

    with get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM outreach
                WHERE status IN ('draft','approved')
                  AND trim(ifnull(to_email,'')) != ''
                ORDER BY
                  CASE
                    WHEN agent_name='brochure' THEN 0
                    WHEN agent_name IN ('blithchron27','blithchron27_local') THEN 1
                    WHEN agent_name='outreach_writer' THEN 2
                    ELSE 3
                  END,
                  id ASC
                LIMIT ?
                """,
                (max_sends,),
            ).fetchall()
        ]

    sent = 0
    errors: list[str] = []
    for row in rows:
        to_email = (row.get("to_email") or "").strip()
        name = row.get("to_name") or to_email
        try:
            activity.log(
                f"Sending pitch → {name} <{to_email}>",
                agent="Closer",
                detail=(row.get("subject") or "")[:200],
                meta={"outreach_id": row["id"], "phase": "sending"},
                step=True,
            )
            send_email(
                to_email=to_email,
                subject=row.get("subject") or "",
                body=row.get("body") or "",
                to_name=row.get("to_name") or "",
            )
            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE outreach
                    SET status='sent', founder_approved=1, sent_at=datetime('now'), send_error=''
                    WHERE id=?
                    """,
                    (row["id"],),
                )
            sent += 1
            activity.bump_finds(sent=1)
            activity.log(
                f"Sent ✓ {name}",
                level="success",
                agent="Closer",
                detail=to_email,
                meta={"outreach_id": row["id"], "to_email": to_email},
            )
            if delay > 0:
                time.sleep(delay)
        except MailerError as exc:
            errors.append(f"{to_email}: {exc}")
            with get_conn() as conn:
                conn.execute(
                    "UPDATE outreach SET send_error=?, status='approved' WHERE id=?",
                    (str(exc)[:400], row["id"]),
                )
            activity.log(
                f"Send failed → {name}",
                level="error",
                agent="Closer",
                detail=str(exc)[:400],
            )
        except Exception as exc:
            errors.append(f"{to_email}: {exc}")
            activity.log(
                f"Send error → {name}: {exc}",
                level="error",
                agent="Closer",
            )

    activity.log(
        f"Closer finished — {sent} sent, {len(errors)} failed, {max(0, max_sends - len(rows))} unused slots",
        level="success" if sent else "warn",
        agent="Closer",
        detail="; ".join(errors[:5]) if errors else "All good",
        meta={"phase": "sending"},
    )
    log_run("Closer", "auto_send", f"Sent {sent} pitches automatically", sent, [])
    return {"sent": sent, "errors": errors, "attempted": len(rows)}


def send_followups(followup_days: int = 3, max_sends: int = 6, delay: float = 1.2) -> dict:
    """Nudge prospects who got a pitch but never replied."""
    if not gmail_ready():
        return {"sent": 0, "errors": ["gmail_not_ready"]}

    sender = sender_profile()
    activity.log(
        f"Checking for follow-ups (no reply after {followup_days}+ days)…",
        agent="Closer",
        step=True,
        meta={"phase": "followup"},
    )
    with get_conn() as conn:
        stale = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM outreach o
                WHERE o.status='sent'
                  AND ifnull(o.reply_status,'none') IN ('none','')
                  AND trim(ifnull(o.to_email,'')) != ''
                  AND o.sent_at IS NOT NULL
                  AND julianday('now') - julianday(o.sent_at) >= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM outreach f
                    WHERE f.agent_name='followup'
                      AND f.target_type=o.target_type
                      AND f.target_id=o.target_id
                      AND f.status IN ('sent','approved','draft')
                  )
                ORDER BY o.sent_at ASC
                LIMIT ?
                """,
                (followup_days, max_sends),
            ).fetchall()
        ]

    sent = 0
    errors: list[str] = []
    for row in stale:
        first = (row.get("to_name") or "there").split()[0]
        subject = "Re: " + (row.get("subject") or "quick follow-up")
        if subject.lower().startswith("re: re:"):
            subject = row.get("subject") or subject
        body = f"""Hi {first},

Just bumping this in case it got buried.

Happy to send a one-page deliverables note or jump on a 10-minute call — whichever is easier.

If timing is off, a one-line reply with the right person also helps a lot.

{_sig(sender)}"""
        to_email = row["to_email"].strip()
        try:
            activity.log(
                f"Follow-up → {row.get('to_name') or to_email}",
                agent="Closer",
                detail=subject,
                step=True,
                meta={"phase": "followup", "parent_id": row["id"]},
            )
            send_email(to_email, subject, body, row.get("to_name") or "")
            with get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO outreach (
                        target_type, target_id, channel, subject, body, status, agent_name,
                        to_name, to_email, from_email, founder_approved, sent_at
                    ) VALUES (?, ?, 'email', ?, ?, 'sent', 'followup', ?, ?, ?, 1, datetime('now'))
                    """,
                    (
                        row["target_type"],
                        row["target_id"],
                        subject,
                        body,
                        row.get("to_name") or "",
                        to_email,
                        sender.get("email") or "",
                    ),
                )
                conn.execute(
                    "UPDATE outreach SET reply_status='followed_up' WHERE id=?",
                    (row["id"],),
                )
            sent += 1
            activity.bump_finds(followups=1, sent=1)
            if delay > 0:
                time.sleep(delay)
        except Exception as exc:
            errors.append(str(exc)[:200])
            activity.log(f"Follow-up failed: {exc}", level="error", agent="Closer")

    if sent:
        activity.log(f"Sent {sent} follow-up pitch(es)", level="success", agent="Closer")
    else:
        activity.log("No follow-ups due this cycle", agent="Closer", level="info")
    return {"sent": sent, "errors": errors}


def _sig(sender: dict) -> str:
    lines = ["Best regards,", sender.get("name") or "Siddharth Patel"]
    if sender.get("email"):
        lines.append(sender["email"])
    if sender.get("phone"):
        lines.append(sender["phone"])
    return "\n".join(lines)


def check_inbox_bounces() -> dict:
    if not gmail_ready():
        return {"bounces": 0}
    activity.log(
        "Checking Gmail for bounce / delivery failures…",
        agent="Closer",
        step=True,
        meta={"phase": "inbox"},
    )
    try:
        result = check_bounces()
        n = int(result.get("outreach_updated") or 0)
        seen = int(result.get("bounces_seen") or 0)
        if n:
            activity.log(
                f"Marked {n} bounce(s) — will skip those addresses",
                level="warn",
                agent="Closer",
                detail=", ".join(result.get("addresses") or [])[:300],
            )
        else:
            activity.log(
                f"Inbox check done ({seen} bounce notice(s) seen, none matched outreach)",
                agent="Closer",
                level="info",
            )
        return result
    except Exception as exc:
        activity.log(f"Bounce check skipped: {exc}", level="warn", agent="Closer")
        return {"bounces": 0, "error": str(exc)[:200]}


def conversion_snapshot() -> dict:
    with get_conn() as conn:
        return {
            "drafts_ready": conn.execute(
                "SELECT COUNT(*) FROM outreach WHERE status IN ('draft','approved') AND trim(ifnull(to_email,''))!=''"
            ).fetchone()[0],
            "sent_total": conn.execute(
                "SELECT COUNT(*) FROM outreach WHERE status='sent'"
            ).fetchone()[0],
            "sent_today": conn.execute(
                "SELECT COUNT(*) FROM outreach WHERE status='sent' AND date(sent_at)=date('now')"
            ).fetchone()[0],
            "awaiting_reply": conn.execute(
                """
                SELECT COUNT(*) FROM outreach
                WHERE status='sent' AND ifnull(reply_status,'none') IN ('none','followed_up','')
                """
            ).fetchone()[0],
            "blithchron_unsent_email": conn.execute(
                """
                SELECT COUNT(*) FROM outreach
                WHERE agent_name IN ('blithchron27','blithchron27_local')
                  AND status!='sent' AND trim(ifnull(to_email,''))!=''
                """
            ).fetchone()[0],
        }


def run_conversion(cfg: dict | None = None) -> dict:
    """Full conversion pass: pitch → auto-send → follow-up → bounce check."""
    c = conversion_config(cfg)
    activity.set_state(phase="converting")
    activity.log(
        "Conversion mode — pitching and messaging clients without waiting for approval",
        level="info",
        agent="Closer",
        step=True,
        meta={"phase": "converting"},
    )

    pitches = prepare_pitches()
    send_stats = {"sent": 0, "errors": [], "attempted": 0}
    follow_stats = {"sent": 0}
    if c["auto_send"]:
        send_stats = auto_send_pitches(c["max_sends_per_cycle"], c["send_delay_seconds"])
        follow_stats = send_followups(
            c["followup_days"],
            max_sends=max(3, c["max_sends_per_cycle"] // 2),
            delay=c["send_delay_seconds"],
        )
    else:
        activity.log(
            "AUTO_SEND is off — pitches prepared but not sent",
            level="warn",
            agent="Closer",
        )

    bounces = check_inbox_bounces()
    snap = conversion_snapshot()
    summary = (
        f"Conversion: {send_stats.get('sent', 0)} new sends, "
        f"{follow_stats.get('sent', 0)} follow-ups · "
        f"{snap['awaiting_reply']} awaiting reply · "
        f"{snap['drafts_ready']} still queued"
    )
    activity.log(summary, level="success", agent="Closer", meta={"phase": "converting", **snap})
    log_run("Closer", "conversion", summary, int(send_stats.get("sent") or 0), [])
    return {
        "pitches": pitches,
        "send": send_stats,
        "followups": follow_stats,
        "bounces": bounces,
        "snapshot": snap,
        "auto_send": c["auto_send"],
    }
