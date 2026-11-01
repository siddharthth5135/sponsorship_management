"""
Reply Watcher — polls Gmail IMAP for replies to our pitches.
Instant founder alert: lead_alerts table + high-priority task + email to Siddharth.
"""

from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from agents import activity
from agents.blacklist import ensure_schema
from agents.orchestrator import add_founder_task, log_run
from app.database import get_conn
from app.services.emails import sender_profile
from app.services.mailer import MailerError, gmail_ready, send_email

SKIP_FROM = (
    "mailer-daemon",
    "postmaster",
    "no-reply",
    "noreply",
    "notifications@",
)


def _decode(val: str | None) -> str:
    if not val:
        return ""
    parts = decode_header(val)
    out = []
    for b, enc in parts:
        if isinstance(b, bytes):
            out.append(b.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(b)
    return "".join(out)


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        chunks = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(chunks)
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")


def _notify_founder(brand: str, from_email: str, snippet: str) -> None:
    """Instant email + in-app alert to Siddharth."""
    ensure_schema()
    profile = sender_profile()
    to_me = (profile.get("email") or "").strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO lead_alerts (brand_name, from_email, snippet, status)
            VALUES (?, ?, ?, 'new')
            """,
            (brand[:200], from_email[:200], snippet[:800]),
        )
    add_founder_task(
        f"🔥 LEAD REPLY: {brand}",
        f"From {from_email}\n\n{snippet[:500]}\n\nOpen Gmail and close this — aim for MoU / call today.",
        "high",
        "reply_watcher",
    )
    activity.log(
        f"LEAD REPLY from {brand}",
        level="success",
        agent="Reply Watcher",
        step=True,
        detail=f"{from_email} — {snippet[:240]}",
        meta={"phase": "lead", "from_email": from_email, "brand": brand},
    )
    if gmail_ready() and to_me:
        try:
            send_email(
                to_me,
                f"[SponsorDesk] LEAD: {brand} replied",
                f"Instant alert — a brand replied to your pitch.\n\nBrand: {brand}\nFrom: {from_email}\n\n---\n{snippet[:1500]}\n---\n\nClose this today if possible.\n",
                "Siddharth",
            )
        except Exception as exc:
            activity.log(f"Could not email alert to you: {exc}", level="warn", agent="Reply Watcher")


def _scan_inbox_replies(user: str, password: str, sent_addrs: dict, our_emails: set[str], limit: int) -> int:
    """Return number of new lead alerts created from one inbox."""
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=45)
    imap.login(user, password)
    matched = 0
    try:
        imap.select("INBOX")
        typ, data = imap.search(None, "(UNSEEN)")
        ids = data[0].split() if typ == "OK" and data and data[0] else []
        if len(ids) < 5:
            typ2, data2 = imap.search(None, "ALL")
            extra = data2[0].split() if typ2 == "OK" and data2 and data2[0] else []
            ids = list(dict.fromkeys(list(ids) + extra[-limit:]))
        ids = ids[-limit:]
        for num in reversed(ids):
            typ, msg_data = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            from_name, from_email = parseaddr(msg.get("From", ""))
            from_email = (from_email or "").lower()
            if not from_email or any(s in from_email for s in SKIP_FROM):
                continue
            if from_email in our_emails:
                continue
            hit = sent_addrs.get(from_email)
            subj = _decode(msg.get("Subject"))
            if not hit:
                domain = from_email.split("@")[-1]
                for addr, row in sent_addrs.items():
                    if addr.endswith("@" + domain) and domain not in ("gmail.com", "yahoo.com", "outlook.com"):
                        hit = row
                        break
            if not hit and subj.lower().startswith("re:"):
                for addr, row in sent_addrs.items():
                    name = (row.get("to_name") or "").lower()
                    if name and name[:12] in subj.lower():
                        hit = row
                        break
            if not hit:
                continue
            body = _body_text(msg)
            snippet = re.sub(r"\s+", " ", body).strip()[:600]
            brand = hit.get("to_name") or from_name or from_email
            with get_conn() as conn:
                exists = conn.execute(
                    """
                    SELECT 1 FROM lead_alerts
                    WHERE lower(from_email)=? AND brand_name=? AND status!='dismissed'
                      AND date(created_at)=date('now')
                    """,
                    (from_email, brand[:200]),
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    """
                    UPDATE outreach SET reply_status='replied'
                    WHERE id=? OR (lower(to_email)=? AND status='sent')
                    """,
                    (hit["id"], (hit.get("to_email") or "").lower()),
                )
                if hit.get("target_type") == "brand" and hit.get("target_id"):
                    conn.execute(
                        "UPDATE brands SET status='interested', conversion_tier='hot', updated_at=datetime('now') WHERE id=?",
                        (hit["target_id"],),
                    )
            _notify_founder(brand, from_email, snippet or subj)
            matched += 1
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return matched


def check_replies(limit: int = 40) -> dict:
    """Poll EVERY ready Gmail inbox for brand replies."""
    from app.services.accounts import ready_accounts

    ensure_schema()
    accounts = ready_accounts()
    if not accounts:
        return {"replies": 0, "error": "gmail_not_ready"}

    activity.log(
        f"Checking {len(accounts)} Gmail inbox(es) for brand replies…",
        agent="Reply Watcher",
        step=True,
        meta={"phase": "inbox"},
    )

    with get_conn() as conn:
        sent_addrs = {
            (r["to_email"] or "").lower(): dict(r)
            for r in conn.execute(
                """
                SELECT id, to_email, to_name, target_id, target_type, subject
                FROM outreach WHERE status='sent' AND trim(ifnull(to_email,''))!=''
                ORDER BY id DESC
                """
            ).fetchall()
        }

    our_emails = {a["email"].lower() for a in accounts}
    matched = 0
    scanned = []
    errors = []
    for acct in accounts:
        user = acct["email"]
        password = (acct.get("gmail_app_password") or "").strip().replace(" ", "")
        try:
            n = _scan_inbox_replies(user, password, sent_addrs, our_emails, limit)
            matched += n
            scanned.append(user)
            activity.log(
                f"Inbox scanned: {user} (+{n} new replies)",
                agent="Reply Watcher",
                level="success" if n else "info",
            )
        except imaplib.IMAP4.error as exc:
            errors.append(f"{user}: {exc}")
            activity.log(f"IMAP failed for {user}: {exc}", level="warn", agent="Reply Watcher")

    activity.log(
        f"Reply Watcher: {matched} new lead reply(ies) across {len(scanned)} inbox(es)",
        level="success" if matched else "info",
        agent="Reply Watcher",
        detail="; ".join(errors) if errors else "OK",
    )
    if matched:
        log_run("Reply Watcher", "replies", f"{matched} brand replies detected", matched, [])
    return {"replies": matched, "alerts": matched, "inboxes": scanned, "errors": errors}


def new_alerts(limit: int = 20) -> list[dict]:
    ensure_schema()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM lead_alerts
            WHERE status='new'
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
