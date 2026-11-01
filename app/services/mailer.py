"""Send outreach emails from the founder's Gmail via SMTP (App Password)."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.emails import sender_profile


class MailerError(Exception):
    """User-facing send failure."""


def gmail_ready() -> bool:
    profile = sender_profile()
    return bool(profile.get("email") and (profile.get("gmail_app_password") or "").strip())


def send_email(to_email: str, subject: str, body: str, to_name: str = "") -> None:
    profile = sender_profile()
    from_email = (profile.get("email") or "").strip()
    password = (profile.get("gmail_app_password") or "").strip().replace(" ", "")
    if not from_email:
        raise MailerError("Sender email is missing in data/sender_profile.json.")
    if not password:
        raise MailerError(
            "Add your Gmail App Password on the Outreach page first "
            "(Google Account → Security → App passwords)."
        )
    if not (to_email or "").strip():
        raise MailerError("This draft has no recipient email. Use LinkedIn / website instead.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or "(no subject)"
    msg["From"] = f"{profile.get('name', 'Siddharth Patel')} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Reply-To"] = from_email
    msg.attach(MIMEText(body or "", "plain", "utf-8"))

    try:
        with _smtp_session(from_email, password) as smtp:
            smtp.sendmail(from_email, [to_email.strip()], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise MailerError(
            "Gmail rejected the login. Create a new App Password at "
            "https://myaccount.google.com/apppasswords and paste it on Outreach."
        ) from exc
    except MailerError:
        raise
    except Exception as exc:
        raise MailerError(f"Could not send: {exc}") from exc


def _smtp_session(from_email: str, password: str):
    smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(from_email, password)
    return smtp


def send_many(messages: list[dict]) -> tuple[int, list[str]]:
    """Send several emails on one SMTP session. messages: to_email, subject, body, to_name, id."""
    profile = sender_profile()
    from_email = (profile.get("email") or "").strip()
    password = (profile.get("gmail_app_password") or "").strip().replace(" ", "")
    if not from_email or not password:
        raise MailerError(
            "Add your Gmail App Password on the Outreach page first "
            "(Google Account → Security → App passwords)."
        )

    sent = 0
    errors: list[str] = []
    try:
        with _smtp_session(from_email, password) as smtp:
            for m in messages:
                to_email = (m.get("to_email") or "").strip()
                if not to_email:
                    errors.append(f"#{m.get('id')}: no email address")
                    continue
                msg = MIMEMultipart("alternative")
                msg["Subject"] = m.get("subject") or "(no subject)"
                msg["From"] = f"{profile.get('name', 'Siddharth Patel')} <{from_email}>"
                to_name = m.get("to_name") or ""
                msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
                msg["Reply-To"] = from_email
                msg.attach(MIMEText(m.get("body") or "", "plain", "utf-8"))
                try:
                    smtp.sendmail(from_email, [to_email], msg.as_string())
                    sent += 1
                    m["_ok"] = True
                except Exception as exc:
                    m["_ok"] = False
                    errors.append(f"{to_email}: {exc}")
    except smtplib.SMTPAuthenticationError as exc:
        raise MailerError(
            "Gmail rejected the login. Create a new App Password at "
            "https://myaccount.google.com/apppasswords and paste it on Outreach."
        ) from exc
    return sent, errors
