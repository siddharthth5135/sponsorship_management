"""
Contact Rescue — when emails bounce ("address not found"), find alternatives
and re-pitch so the brand still hears: we want you on the Blithchron sponsor board.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from agents import activity
from agents.orchestrator import log_run
from app.database import get_conn, init_db
from app.services.emails import (
    BLITHCHRON_BROCHURE_URL,
    blithchron_brochure_email,
    sender_profile,
)
from app.services.mailer import MailerError, gmail_ready, send_email
from app.services.messaging import pitch_text

# Hand-verified alternates from public pages / MCA / LinkedIn (Mar 2026 rescue)
KNOWN_ALTS: dict[str, dict] = {
    "info@ajwafoodproducts.com": {
        "brand_match": "Ajwa",
        "emails": ["ajwafood777@gmail.com", "info@ajwafoodproduct.com"],
        "phone": "+91 98259 68882",
        "note": "MCA email + site phone; products@ domain bounced",
    },
    "mkt@siporabeverages.com": {
        "brand_match": "Sipora",
        "emails": ["info@siporabeverages.com"],
        "phone": "+91 98702 48247",
        "note": "LinkedIn company lists info@; mkt@ bounced",
    },
    "freshqo@goodant.io": {
        "brand_match": "FreshQo",
        "emails": [],  # no public alt email — phone/WA only
        "phone": "+91 91732 24828",
        "note": "Site email dead; franchise phone for WhatsApp pitch",
    },
    "partners@globaltechtrums.com": {
        "brand_match": "Saaras",
        "emails": ["sales@globaltechtrums.com", "piyush@globaltechtrums.com"],
        "phone": "+91 81088 74090",
        "note": "partners@ bounced; sales + founder public on site",
    },
    "sponsor@sparshsvnit.org": {
        "brand_match": "Sparsh",
        "emails": ["sparsh@svnit.ac.in", "cultural@svnit.ac.in"],
        "phone": "",
        "note": "Fest sponsor inbox dead; try SVNIT cultural routes",
    },
    "info@gscon2027.org": {
        "brand_match": "GSCON",
        "emails": ["ieeegscon@gmail.com", "contact@ieeegscon.org"],
        "phone": "",
        "note": "Conference inbox dead; public IEEE GSCON routes",
    },
}


def _clean_url(href: str) -> str:
    href = href.replace("&amp;", "&")
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) or href
    return href


def _search(query: str, max_results: int = 8) -> list[dict]:
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "in-en"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=25,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return []
    html = resp.text
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div|span)>', html, re.DOTALL)
    out = []
    for i, (href, raw_title) in enumerate(links[:max_results]):
        out.append(
            {
                "title": unescape(re.sub(r"<[^>]+>", "", raw_title)).strip(),
                "url": _clean_url(href),
                "snippet": unescape(re.sub(r"<[^>]+>", "", snippets[i])).strip() if i < len(snippets) else "",
            }
        )
    return out


def _emails_in_text(text: str) -> list[str]:
    found = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text or "")
    skip = ("example.com", "sentry.", "wixpress", "schema.org", "godaddy", "domain.com")
    clean = []
    for e in found:
        el = e.lower()
        if any(s in el for s in skip):
            continue
        if el not in clean:
            clean.append(el)
    return clean


def discover_alt_emails(brand_name: str, website: str = "", dead_email: str = "") -> list[str]:
    queries = [
        f'"{brand_name}" email OR contact OR sponsorship OR marketing India',
        f"{brand_name} contact email",
    ]
    if website:
        queries.append(f"site:{urlparse(website).netloc or website} email OR contact")
    emails: list[str] = []
    dead = (dead_email or "").lower()
    for q in queries:
        activity.log(f"Rescue search: {q}", agent="Contact Rescue", step=True, meta={"phase": "rescue"})
        for hit in _search(q):
            for e in _emails_in_text(f"{hit['title']} {hit['snippet']} {hit['url']}"):
                if e != dead and e not in emails:
                    emails.append(e)
    return emails[:5]


def onboard_pitch(brand: dict, sender: dict | None = None) -> tuple[str, str]:
    """Strong 'we want you on the sponsor board' + brochure."""
    sender = sender or sender_profile()
    name = brand.get("name") or "your brand"
    first = (brand.get("contact_name") or "").strip().split()[:1]
    greet = f"Hi {first[0]}," if first and first[0].lower() not in ("team", "marketing") else f"Hi {name} team,"
    package = brand.get("package") or brand.get("category") or "Associate / Event Sponsor"
    ask = brand.get("ask_inr") or "a flexible package"
    subject = f"We want {name} on the Blithchron '27 sponsor board — IITGN"
    body = f"""{greet}

I'm {sender['name'].split()[0]}. I'm writing again because we specifically want {name} on the Blithchron '27 sponsorship board at IIT Gandhinagar (4–7 February 2027).

Blithchron is IITGN's annual cultural fest — ~22,000 footfall, two Pronites (6,000+ a night), 100+ partner colleges across Gujarat. Past associates include Central Bank of India (Title '25), Coca-Cola, Monster, Maggi and The Souled Store.

Official sponsorship brochure (tiers, deliverables, past sponsors):
{BLITHCHRON_BROCHURE_URL}

For {name} we're proposing: {package} (indicative band {ask}).

Important for you: there is 0 brokerage fee from the brand side. You only pay the fest for the package you approve. Our commission is handled with the event.

We'd love to lock a category / package for {name} early. Could we do a 10-minute call this week, or reply with the right campus/brand person?

Best regards,
{sender.get('name') or 'Siddharth Patel'}
{sender.get('email') or ''}
{sender.get('phone') or ''}"""
    return subject, body


def list_bounced_targets() -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT o.id AS outreach_id, o.to_email, o.to_name, o.agent_name, o.target_type, o.target_id,
                   o.send_error, b.name AS brand_name, b.website, b.contact_phone, b.segment,
                   b.contact_name, b.category, b.notes, b.description
            FROM outreach o
            LEFT JOIN brands b ON o.target_type='brand' AND b.id = o.target_id
            WHERE o.status='bounced' OR lower(COALESCE(o.send_error,'')) LIKE '%not found%'
               OR lower(COALESCE(o.send_error,'')) LIKE '%undeliverable%'
            ORDER BY o.id DESC
            """
        ).fetchall()
    # Unique by dead email
    seen = set()
    out = []
    for r in rows:
        d = dict(r)
        key = (d.get("to_email") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def apply_rescue_and_send(dry_run: bool = False) -> dict:
    """Find alts for bounced addresses, update CRM, send onboard pitch + brochure."""
    init_db()
    sender = sender_profile()
    targets = list_bounced_targets()
    activity.log(
        f"Contact Rescue starting — {len(targets)} unique dead inbox(es)",
        agent="Contact Rescue",
        step=True,
        meta={"phase": "rescue"},
    )
    stats = {
        "targets": len(targets),
        "rescued_email": 0,
        "phone_only": 0,
        "sent": 0,
        "errors": [],
        "details": [],
    }
    if not targets:
        activity.log("No bounced targets to rescue", agent="Contact Rescue", level="info")
        return stats

    ready = gmail_ready()
    for t in targets:
        dead = (t.get("to_email") or "").strip().lower()
        brand_id = t.get("target_id")
        name = t.get("brand_name") or t.get("to_name") or dead
        known = KNOWN_ALTS.get(dead) or {}
        alts = list(known.get("emails") or [])
        phone = known.get("phone") or t.get("contact_phone") or ""

        # Web discovery for more emails
        discovered = discover_alt_emails(name, t.get("website") or "", dead)
        for e in discovered:
            if e not in alts and e != dead:
                alts.append(e)

        detail = {
            "brand": name,
            "dead": dead,
            "alts": alts,
            "phone": phone,
            "note": known.get("note") or "",
        }
        activity.log(
            f"Rescue plan for {name}",
            agent="Contact Rescue",
            detail=f"Dead: {dead} → alts: {', '.join(alts) or 'none'} · phone: {phone or '—'}",
            meta={"phase": "rescue", **detail},
        )

        brand = {
            "id": brand_id,
            "name": name,
            "contact_name": t.get("contact_name") or t.get("to_name") or "",
            "contact_email": alts[0] if alts else "",
            "contact_phone": phone,
            "package": t.get("category") or "Associate / Event Sponsor",
            "ask_inr": "a flexible package",
            "category": t.get("category") or "",
            "segment": t.get("segment") or "",
        }

        if brand_id and t.get("target_type") == "brand":
            with get_conn() as conn:
                notes_extra = f"Rescue {dead} → {alts[0] if alts else 'PHONE/WA'} ({known.get('note') or 'web'})"
                if alts:
                    conn.execute(
                        """
                        UPDATE brands SET contact_email=?, contact_phone=COALESCE(NULLIF(?,''), contact_phone),
                          notes=trim(COALESCE(notes,'') || ' | ' || ?), updated_at=datetime('now')
                        WHERE id=?
                        """,
                        (alts[0], phone, notes_extra[:300], brand_id),
                    )
                    stats["rescued_email"] += 1
                elif phone:
                    conn.execute(
                        """
                        UPDATE brands SET contact_email='', contact_phone=COALESCE(NULLIF(?,''), contact_phone),
                          notes=trim(COALESCE(notes,'') || ' | ' || ?), updated_at=datetime('now')
                        WHERE id=?
                        """,
                        (phone, notes_extra[:300], brand_id),
                    )
                    stats["phone_only"] += 1

        if alts and ready and not dry_run:
            for alt in alts[:2]:  # try up to 2 alternates
                subject, body = onboard_pitch({**brand, "contact_email": alt}, sender)
                try:
                    activity.log(
                        f"Re-pitching {name} → {alt}",
                        agent="Contact Rescue",
                        step=True,
                        detail="Want you on Blithchron sponsor board + brochure",
                        meta={"phase": "sending"},
                    )
                    send_email(alt, subject, body, brand.get("contact_name") or name)
                    with get_conn() as conn:
                        conn.execute(
                            """
                            INSERT INTO outreach (
                                target_type, target_id, channel, subject, body, status, agent_name,
                                to_name, to_email, from_email, founder_approved, sent_at
                            ) VALUES (?, ?, 'email', ?, ?, 'sent', 'contact_rescue', ?, ?, ?, 1, datetime('now'))
                            """,
                            (
                                t.get("target_type") or "brand",
                                brand_id or 0,
                                subject,
                                body,
                                brand.get("contact_name") or name,
                                alt,
                                sender.get("email") or "",
                            ),
                        )
                        # Clear bounce flag on old rows for this dead address
                        conn.execute(
                            """
                            UPDATE outreach SET send_error=?, reply_status='rescued'
                            WHERE lower(to_email)=? AND status='bounced'
                            """,
                            (f"Rescued → sent to {alt}", dead),
                        )
                    stats["sent"] += 1
                    activity.log(
                        f"Rescue sent ✓ {name} <{alt}>",
                        level="success",
                        agent="Contact Rescue",
                        detail=alt,
                    )
                    break  # one successful alt is enough
                except MailerError as exc:
                    stats["errors"].append(f"{alt}: {exc}")
                    activity.log(f"Rescue send failed {alt}: {exc}", level="error", agent="Contact Rescue")
                except Exception as exc:
                    stats["errors"].append(f"{alt}: {exc}")
                    activity.log(f"Rescue error {alt}: {exc}", level="error", agent="Contact Rescue")
        elif not alts and phone:
            # WhatsApp-ready log for founder / Blithchron page
            text = pitch_text(brand) if brand.get("name") else onboard_pitch(brand)[1]
            activity.log(
                f"WhatsApp rescue for {name} — no working email",
                level="warn",
                agent="Contact Rescue",
                detail=f"Phone {phone}. Pitch: {text[:180]}… Brochure: {BLITHCHRON_BROCHURE_URL}",
                meta={"channel": "whatsapp", "phone": phone, "brand": name},
            )
            stats["phone_only"] += 1 if "phone_only" not in str(detail) else 0
        elif not ready:
            stats["errors"].append("gmail_not_ready")

        stats["details"].append(detail)

    summary = (
        f"Rescue done: {stats['rescued_email']} email alts, {stats['sent']} re-sent, "
        f"{stats['phone_only']} phone/WA, {len(stats['errors'])} errors"
    )
    activity.log(summary, level="success", agent="Contact Rescue", step=True, meta={"phase": "idle"})
    log_run("Contact Rescue", "bounce_rescue", summary, stats["sent"], [])
    return stats


if __name__ == "__main__":
    import json

    print(json.dumps(apply_rescue_and_send(), indent=2, default=str))
