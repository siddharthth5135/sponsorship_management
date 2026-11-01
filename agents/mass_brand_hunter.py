"""
Mass Brand Hunter — harvest Gujarat (esp. Ahmedabad / Gandhinagar) MSME, SME,
startup and brand contacts that fit campus/festival sponsorship.

Finds REAL public emails from web search — never invents addresses.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from agents import activity
from agents.blacklist import is_dead
from agents.orchestrator import log_run
from app.database import get_conn, init_db
from app.services.emails import BLITHCHRON_BROCHURE_URL, sender_profile
from app.services.mailer import MailerError, gmail_ready, send_email

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

SKIP_EMAIL = (
    "example.com", "sentry.", "wixpress", "schema.org", "godaddy", "domain.com",
    "email.com", "yourdomain", "company.com", "test@", "noreply@", "no-reply@",
    "donotreply", "privacy@", "legal@", "support@google", "github.com",
)

CITIES = (
    "Ahmedabad", "Gandhinagar", "Sanand", "Changodar", "Naroda", "Vatva",
    "Odhav", "GIDC Ahmedabad", "SG Highway", "Bopal", "Thaltej", "Prahlad Nagar",
)

CATEGORIES = (
    "startup", "MSME", "SME", "D2C brand", "FMCG", "cafe", "restaurant",
    "edtech", "fintech", "saas", "coaching institute", "gym", "salon",
    "real estate", "bank", "NBFC", "insurance", "automobile dealer",
    "electronics", "fashion", "jewellery", "pharmacy", "hospital",
    "logistics", "manufacturing", "textile", "chemical", "packaging",
    "event management", "printing", "IT company", "digital marketing agency",
    "food brand", "beverage", "dairy", "namkeen", "bakery", "cloud kitchen",
)


def _queries(limit: int = 120) -> list[str]:
    qs = []
    for city in CITIES:
        for cat in CATEGORIES:
            qs.append(f"{cat} {city} contact email OR marketing@ OR info@")
            qs.append(f"{cat} {city} Gujarat sponsorship OR brand partnerships email")
            if len(qs) >= limit:
                return qs
    return qs


def _clean_url(href: str) -> str:
    href = href.replace("&amp;", "&")
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) or href
    return href


def _parse_ddg(html: str, max_results: int) -> list[dict]:
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


def _parse_bing(html: str, max_results: int) -> list[dict]:
    # Bing organic results
    blocks = re.findall(
        r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<p>|class="b_caption"[^>]*>)(.*?)(?:</p>|</div>)',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    out = []
    for href, raw_title, raw_snip in blocks[:max_results]:
        out.append(
            {
                "title": unescape(re.sub(r"<[^>]+>", "", raw_title)).strip(),
                "url": href,
                "snippet": unescape(re.sub(r"<[^>]+>", "", raw_snip)).strip(),
            }
        )
    if out:
        return out
    # Fallback: any mailto / emails on page + links
    for m in re.finditer(r'href="(https?://[^"]+)"[^>]*>([^<]{3,120})</a>', html):
        out.append({"title": unescape(m.group(2)).strip(), "url": m.group(1), "snippet": ""})
        if len(out) >= max_results:
            break
    return out


def _search(query: str, max_results: int = 15) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    # 1) Bing
    try:
        resp = httpx.get(
            "https://www.bing.com/search",
            params={"q": query, "setlang": "en-in"},
            headers=headers,
            timeout=20,
            follow_redirects=True,
        )
        if resp.status_code < 400:
            got = _parse_bing(resp.text, max_results)
            if got:
                return got
    except Exception:
        pass
    # 2) DuckDuckGo HTML
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "in-en"},
            headers=headers,
            timeout=20,
            follow_redirects=True,
        )
        if resp.status_code < 400:
            got = _parse_ddg(resp.text, max_results)
            if got:
                return got
    except Exception:
        pass
    return []


def _valid_emails(text: str) -> list[str]:
    found = []
    for e in EMAIL_RE.findall(text or ""):
        el = e.lower().strip(".")
        if any(s in el for s in SKIP_EMAIL):
            continue
        if el.endswith((".png", ".jpg", ".gif", ".js", ".css")):
            continue
        if is_dead(el):
            continue
        if el not in found:
            found.append(el)
    return found


def _guess_city(blob: str) -> str:
    lower = blob.lower()
    for c in ("Gandhinagar", "Sanand", "Surat", "Vadodara", "Rajkot", "Ahmedabad"):
        if c.lower() in lower:
            return c
    return "Ahmedabad"


def _guess_category(blob: str) -> str:
    lower = blob.lower()
    for cat in CATEGORIES:
        if cat.lower() in lower:
            return cat.title()
    return "Local brand / MSME"


def _brand_name_from_hit(title: str, email: str) -> str:
    t = re.sub(r"\s*[\|\-–:].*$", "", title or "").strip()
    if t and len(t) > 2:
        return t[:160]
    local = email.split("@")[0]
    return local.replace(".", " ").replace("_", " ").title()[:120]


def hard_onboard_email(brand: dict, sender: dict | None = None) -> tuple[str, str]:
    sender = sender or sender_profile()
    name = brand.get("name") or "your brand"
    subject = f"{name} — we want you on Blithchron '27 (IIT Gandhinagar) sponsor board"
    body = f"""Hi {name} team,

I'm {sender['name'].split()[0]}. We're filling sponsor slots for Blithchron '27 — IIT Gandhinagar's annual cultural fest (4–7 February 2027).

Why this fits brands like yours in Ahmedabad / Gandhinagar:
• ~22,000 footfall · two Pronites (6,000+/night) · 100+ partner colleges
• Past associates: Central Bank of India (Title '25), Coca-Cola, Monster, Maggi, The Souled Store
• 0 brokerage fee from the brand side — you only pay the fest for the package you approve

Official brochure:
{BLITHCHRON_BROCHURE_URL}

We want {name} on the sponsor board this year (Associate / stall / sampling / category exclusive — flexible for MSMEs & startups).

Reply YES + a time for a 10-min call, or forward to the right marketing person. First-come on category locks.

Best regards,
{sender.get('name') or 'Siddharth Patel'}
{sender.get('email') or ''}
{sender.get('phone') or ''}"""
    return subject, body


def upsert_mass_brand(conn, name: str, email: str, city: str, category: str, website: str, source: str) -> bool:
    email = email.lower().strip()
    if is_dead(email):
        return False
    exists = conn.execute(
        """
        SELECT id FROM brands
        WHERE lower(contact_email)=? OR (lower(name)=? AND segment='mass_gujarat')
        """,
        (email, name.lower()),
    ).fetchone()
    if exists:
        return False
    conn.execute(
        """
        INSERT INTO brands (
            name, city, category, goal, status, contact_email, website, source_url,
            discovery_reason, description, segment, conversion_tier, intent_signal, notes
        ) VALUES (?, ?, ?, 'awareness', 'prospect', ?, ?, ?, ?, ?, 'mass_gujarat', 'warm', 'active', ?)
        """,
        (
            name[:180],
            city,
            category[:80],
            email,
            website[:300],
            website[:300],
            f"Mass hunter via {source}"[:400],
            f"Gujarat sponsorship prospect ({category})"[:400],
            "Auto-found for Blithchron hard pitch. Verify before MoU.",
        ),
    )
    return True


def queue_hard_pitch(conn, brand_id: int, brand: dict, sender: dict) -> bool:
    email = (brand.get("contact_email") or "").strip().lower()
    if not email or is_dead(email):
        return False
    existing = conn.execute(
        """
        SELECT id, status FROM outreach
        WHERE target_type='brand' AND target_id=? AND agent_name='mass_pitch'
        ORDER BY id DESC LIMIT 1
        """,
        (brand_id,),
    ).fetchone()
    if existing and existing["status"] == "sent":
        return False
    subject, body = hard_onboard_email(brand, sender)
    if existing:
        conn.execute(
            """
            UPDATE outreach SET subject=?, body=?, to_email=?, to_name=?, from_email=?,
              status='approved', founder_approved=1, send_error=''
            WHERE id=?
            """,
            (subject, body, email, brand.get("name") or "", sender.get("email") or "", existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO outreach (
                target_type, target_id, channel, subject, body, status, agent_name,
                to_name, to_email, from_email, founder_approved
            ) VALUES ('brand', ?, 'email', ?, ?, 'approved', 'mass_pitch', ?, ?, ?, 1)
            """,
            (brand_id, subject, body, brand.get("name") or "", email, sender.get("email") or ""),
        )
    return True


def run_mass_hunt(max_queries: int = 80, progress=None) -> dict:
    init_db()
    from agents.blacklist import ensure_schema

    ensure_schema()
    sender = sender_profile()
    stats = {"queries": 0, "emails_seen": 0, "brands_added": 0, "pitches_queued": 0, "rejected_dead": 0}
    queries = _queries(max_queries)

    activity.log(
        f"Mass Brand Hunter starting — up to {len(queries)} Gujarat MSME/startup searches",
        agent="Mass Hunter",
        step=True,
        meta={"phase": "hunting"},
    )

    with get_conn() as conn:
        for q in queries:
            stats["queries"] += 1
            if progress:
                try:
                    progress(f"Hunting: {q}", agent="Mass Hunter", phase="hunting")
                except Exception:
                    pass
            for hit in _search(q):
                blob = f"{hit['title']} {hit['snippet']} {hit['url']}"
                emails = _valid_emails(blob)
                # Also try fetching the page lightly for contact emails (short timeout)
                if hit["url"].startswith("http") and len(emails) < 2:
                    try:
                        page = httpx.get(
                            hit["url"],
                            timeout=8,
                            follow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        if page.status_code < 400:
                            emails = list(dict.fromkeys(emails + _valid_emails(page.text[:80000])))
                    except Exception:
                        pass
                for email in emails[:3]:
                    stats["emails_seen"] += 1
                    if is_dead(email):
                        stats["rejected_dead"] += 1
                        continue
                    name = _brand_name_from_hit(hit["title"], email)
                    city = _guess_city(blob + " " + q)
                    cat = _guess_category(blob + " " + q)
                    if upsert_mass_brand(conn, name, email, city, cat, hit["url"], q):
                        stats["brands_added"] += 1
                        row = conn.execute(
                            "SELECT id FROM brands WHERE lower(contact_email)=?",
                            (email,),
                        ).fetchone()
                        if row and queue_hard_pitch(
                            conn,
                            row["id"],
                            {"name": name, "contact_email": email, "category": cat},
                            sender,
                        ):
                            stats["pitches_queued"] += 1

    activity.log(
        f"Mass hunt done — +{stats['brands_added']} brands, {stats['pitches_queued']} hard pitches queued",
        level="success",
        agent="Mass Hunter",
        detail=f"Queries {stats['queries']} · emails seen {stats['emails_seen']} · skipped dead {stats['rejected_dead']}",
        meta={"phase": "hunting", **stats},
    )
    log_run("Mass Hunter", "hunt", f"Added {stats['brands_added']} brands", stats["brands_added"], [])
    return stats


def send_mass_queue(max_sends: int = 80, delay: float = 0.7, daily_cap: int = 400) -> dict:
    """Blast queued mass_pitch + other approved drafts, respecting daily Gmail quota + blacklist."""
    from agents.blacklist import bump_sent, remaining_quota

    if not gmail_ready():
        return {"sent": 0, "errors": ["gmail_not_ready"]}
    left = remaining_quota(daily_cap)
    if left <= 0:
        activity.log(
            f"Daily Gmail cap reached ({daily_cap}). Pausing sends until tomorrow.",
            level="warn",
            agent="Closer",
            step=True,
        )
        return {"sent": 0, "errors": ["daily_cap"], "remaining_quota": 0}

    max_sends = min(max_sends, left)
    activity.log(
        f"Hard-pitch blast — up to {max_sends} (quota left today {left})",
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
                  AND lower(to_email) NOT IN (SELECT email FROM dead_emails)
                ORDER BY
                  CASE agent_name
                    WHEN 'contact_rescue' THEN 0
                    WHEN 'brochure' THEN 1
                    WHEN 'mass_pitch' THEN 2
                    WHEN 'blithchron27' THEN 3
                    WHEN 'blithchron27_local' THEN 4
                    ELSE 5
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
        to_email = (row.get("to_email") or "").strip().lower()
        if is_dead(to_email):
            continue
        try:
            send_email(to_email, row.get("subject") or "", row.get("body") or "", row.get("to_name") or "")
            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE outreach SET status='sent', founder_approved=1,
                      sent_at=datetime('now'), send_error='' WHERE id=?
                    """,
                    (row["id"],),
                )
            bump_sent(1)
            sent += 1
            activity.bump_finds(sent=1)
            activity.log(
                f"Hard pitch sent → {row.get('to_name') or to_email}",
                level="success",
                agent="Closer",
                detail=to_email,
            )
            if delay:
                import time

                time.sleep(delay)
        except MailerError as exc:
            msg = str(exc).lower()
            errors.append(f"{to_email}: {exc}")
            if "not found" in msg or "undeliverable" in msg or "rejected" in msg:
                from agents.blacklist import mark_dead

                mark_dead(to_email, str(exc)[:200], row.get("target_id"))
            with get_conn() as conn:
                conn.execute(
                    "UPDATE outreach SET send_error=?, status='approved' WHERE id=?",
                    (str(exc)[:400], row["id"]),
                )
        except Exception as exc:
            errors.append(f"{to_email}: {exc}")

    activity.log(
        f"Hard-pitch blast finished — {sent} sent, {len(errors)} failed, quota left {remaining_quota(daily_cap)}",
        level="success" if sent else "warn",
        agent="Closer",
    )
    return {"sent": sent, "errors": errors, "remaining_quota": remaining_quota(daily_cap)}


if __name__ == "__main__":
    import json

    print(json.dumps(run_mass_hunt(40), indent=2))
