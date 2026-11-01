"""Read Gmail for delivery-failure (bounce) messages and map them to outreach rows.

SMTP "sent" only means Gmail accepted the message. Real failures often arrive later
as Mail Delivery Subsystem emails — this checker picks those up via IMAP.
"""

from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from app.database import get_conn
from app.services.emails import sender_profile
from app.services.mailer import MailerError

BOUNCE_FROM = (
    "mailer-daemon@googlemail.com",
    "mailer-daemon@gmail.com",
    "postmaster@",
)

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
FAILED_TO_RE = re.compile(
    r"(?:wasn't delivered to|was not delivered to|failed permanently|Address not found|"
    r"does not exist|The email account that you tried to reach does not exist|"
    r"Delivery to the following recipient(?:s)? failed|"
    r"Final-Recipient:\s*rfc822;\s*)"
    r"[<\s]*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
    re.I,
)
REASON_RE = re.compile(
    r"(Address not found|domain .+ couldn't be found|does not exist|"
    r"user unknown|mailbox unavailable|permanent error|"
    r"550[- ].{10,120})",
    re.I,
)


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return str(part.get_payload() or "")
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _message_text(msg: email.message.Message) -> str:
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html", "message/delivery-status"):
                chunks.append(_decode_part(part))
    else:
        chunks.append(_decode_part(msg))
    return "\n".join(chunks)


def _extract_failed_addresses(text: str) -> list[str]:
    found: list[str] = []
    for m in FAILED_TO_RE.finditer(text):
        addr = m.group(1).lower().strip()
        if addr not in found and "googlemail" not in addr and "mailer-daemon" not in addr:
            found.append(addr)
    if not found:
        # Fallback: emails mentioned near failure keywords
        lower = text.lower()
        if any(k in lower for k in ("wasn't delivered", "address not found", "could not be found", "550-")):
            for addr in EMAIL_RE.findall(text):
                a = addr.lower()
                if any(x in a for x in ("mailer-daemon", "googlemail.com", "gmail.com", "postmaster")):
                    continue
                if a not in found:
                    found.append(a)
    return found


def _extract_reason(text: str) -> str:
    m = REASON_RE.search(text.replace("\n", " "))
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip()[:220]
    return "Delivery failed (bounce from Gmail Mail Delivery Subsystem)"


def _scan_account_bounces(user: str, password: str, limit: int) -> list[dict]:
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=45)
    imap.login(user, password)
    bounce_hits: list[dict] = []
    try:
        imap.select("INBOX")
        typ, data = imap.search(None, '(FROM "mailer-daemon")')
        if typ != "OK" or not data or not data[0]:
            typ, data = imap.search(None, '(FROM "mailer-daemon@googlemail.com")')
        ids = data[0].split() if data and data[0] else []
        ids = ids[-limit:]
        for num in reversed(ids):
            typ, msg_data = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            text = _message_text(msg)
            addrs = _extract_failed_addresses(text)
            if not addrs:
                continue
            reason = _extract_reason(text)
            subj = msg.get("Subject", "")
            if isinstance(subj, str):
                decoded = decode_header(subj)
                subj = "".join(
                    (b.decode(c or "utf-8", errors="replace") if isinstance(b, bytes) else b)
                    for b, c in decoded
                )
            when = msg.get("Date", "")
            try:
                when_iso = parsedate_to_datetime(when).isoformat() if when else ""
            except Exception:
                when_iso = when
            for addr in addrs:
                bounce_hits.append(
                    {
                        "email": addr,
                        "reason": reason,
                        "subject": subj,
                        "bounced_at": when_iso,
                        "inbox": user,
                    }
                )
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return bounce_hits


def check_bounces(limit: int = 40) -> dict:
    """Scan bounce mail in EVERY configured Gmail account."""
    from app.services.accounts import ready_accounts

    accounts = ready_accounts()
    if not accounts:
        raise MailerError(
            "Add Gmail App Passwords on Outreach for your accounts. Also enable IMAP on each Gmail."
        )

    bounce_hits: list[dict] = []
    errors: list[str] = []
    for acct in accounts:
        user = acct["email"]
        password = (acct.get("gmail_app_password") or "").strip().replace(" ", "")
        try:
            bounce_hits.extend(_scan_account_bounces(user, password, limit))
        except imaplib.IMAP4.error as exc:
            errors.append(f"{user}: {exc}")

    if not bounce_hits and errors and not accounts:
        raise MailerError("; ".join(errors))

    updated = 0
    matched: list[str] = []
    with get_conn() as conn:
        for hit in bounce_hits:
            rows = conn.execute(
                """
                SELECT id, status, to_email FROM outreach
                WHERE lower(to_email)=?
                ORDER BY id DESC
                """,
                (hit["email"],),
            ).fetchall()
            for row in rows:
                if row["status"] not in ("sent", "bounced", "approved", "draft"):
                    continue
                if row["status"] == "draft":
                    continue
                note = f"Bounce: {hit['reason']} (Gmail reported {hit['email']} undeliverable)"
                conn.execute(
                    """
                    UPDATE outreach
                    SET status='bounced', send_error=?, founder_approved=1
                    WHERE id=?
                    """,
                    (note[:500], row["id"]),
                )
                updated += 1
                matched.append(hit["email"])
                break

    return {
        "bounces_seen": len(bounce_hits),
        "unique_failed": len({h["email"] for h in bounce_hits}),
        "outreach_updated": updated,
        "addresses": sorted(set(matched)),
        "inboxes_scanned": [a["email"] for a in accounts],
        "errors": errors,
    }
