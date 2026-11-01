"""Send outreach emails via Gmail SMTP — rotates across configured accounts."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.accounts import any_gmail_ready, pick_sender, ready_accounts
from app.services.emails import sender_profile


class MailerError(Exception):
    """User-facing send failure."""


def gmail_ready() -> bool:
    return any_gmail_ready()


def send_email(to_email: str, subject: str, body: str, to_name: str = "", account: dict | None = None) -> str:
    """Send one email. Returns the from_email used."""
    if account is None:
        try:
            account = pick_sender()
        except ValueError as exc:
            raise MailerError(
                "Add Gmail App Passwords on Outreach for siddharththpatel@gmail.com "
                "and/or siddharthth5135@gmail.com "
                "(Google Account → Security → App passwords)."
            ) from exc
    from_email = (account.get("email") or "").strip()
    password = (account.get("gmail_app_password") or "").strip().replace(" ", "")
    display = account.get("name") or sender_profile().get("name") or "Siddharth Patel"
    if not from_email or not password:
        raise MailerError("Selected Gmail account is missing an App Password.")
    if not (to_email or "").strip():
        raise MailerError("This draft has no recipient email. Use LinkedIn / website instead.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or "(no subject)"
    msg["From"] = f"{display} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Reply-To"] = from_email
    msg.attach(MIMEText(body or "", "plain", "utf-8"))

    try:
        with _smtp_session(from_email, password) as smtp:
            smtp.sendmail(from_email, [to_email.strip()], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise MailerError(
            f"Gmail rejected login for {from_email}. Create a new App Password at "
            "https://myaccount.google.com/apppasswords (while signed into THAT Google account)."
        ) from exc
    except MailerError:
        raise
    except Exception as exc:
        raise MailerError(f"Could not send from {from_email}: {exc}") from exc
    return from_email


def _smtp_session(from_email: str, password: str):
    smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(from_email, password)
    return smtp


def send_many(messages: list[dict]) -> tuple[int, list[str]]:
    """Send several emails rotating accounts. Sets m['_ok'] and m['_from_email']."""
    ready = ready_accounts()
    if not ready:
        raise MailerError(
            "Add Gmail App Passwords on Outreach for your Gmail accounts first."
        )

    sent = 0
    errors: list[str] = []
    profile = sender_profile()
    display = profile.get("name") or "Siddharth Patel"

    # Open one SMTP session per account and round-robin messages
    sessions: list[tuple[dict, smtplib.SMTP]] = []
    try:
        for acct in ready:
            password = (acct.get("gmail_app_password") or "").strip().replace(" ", "")
            sessions.append((acct, _smtp_session(acct["email"], password)))
        for i, m in enumerate(messages):
            to_email = (m.get("to_email") or "").strip()
            if not to_email:
                errors.append(f"#{m.get('id')}: no email address")
                m["_ok"] = False
                continue
            acct, smtp = sessions[i % len(sessions)]
            from_email = acct["email"]
            msg = MIMEMultipart("alternative")
            msg["Subject"] = m.get("subject") or "(no subject)"
            msg["From"] = f"{display} <{from_email}>"
            to_name = m.get("to_name") or ""
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            msg["Reply-To"] = from_email
            msg.attach(MIMEText(m.get("body") or "", "plain", "utf-8"))
            try:
                smtp.sendmail(from_email, [to_email], msg.as_string())
                sent += 1
                m["_ok"] = True
                m["_from_email"] = from_email
            except Exception as exc:
                m["_ok"] = False
                errors.append(f"{to_email} via {from_email}: {exc}")
    except smtplib.SMTPAuthenticationError as exc:
        raise MailerError(
            "Gmail rejected a login. Check App Passwords for both accounts on Outreach."
        ) from exc
    finally:
        for _, smtp in sessions:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass
    return sent, errors
