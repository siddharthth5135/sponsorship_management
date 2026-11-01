"""Seed thousands of Gujarat sponsorship prospects from public local lists + contact-page scrape."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.blacklist import ensure_schema, is_dead
from agents.mass_brand_hunter import hard_onboard_email, queue_hard_pitch, upsert_mass_brand
from app.database import get_conn, init_db
from app.services.emails import sender_profile
from scripts.blithchron_leads_master import LEADS
from scripts.blithchron_local_leads import LOCAL_LEADS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Public / commonly published marketing inboxes for AMD-GN style categories (expand aggressively)
DOMAIN_SEEDS = [
    # Existing pack domains + Gujarat MSME-style public sites
    ("https://samratnamkeen.com/contact", "Samrat Namkeen", "Ahmedabad", "FMCG"),
    ("https://mannfoods.in/contact", "Mann Foods", "Ahmedabad", "Snacks"),
    ("https://toskachocolates.com/pages/contact", "Toska Chocolates", "Ahmedabad", "Chocolate"),
    ("https://www.sankalpfoods.com/contact/", "Sankalp Foods", "Ahmedabad", "F&B"),
    ("https://tirupatiagrotech.com/contact-us/", "Tirupati Agrotech", "Ahmedabad", "FMCG"),
    ("https://junctioncafe.in/contact", "Junction Cafe", "Ahmedabad", "Cafe"),
    ("https://varietea.in/contact/", "Varietea", "Ahmedabad", "Cafe"),
    ("https://www.thechocolateroomindia.com/contact-us/", "The Chocolate Room", "Ahmedabad", "Cafe"),
    ("https://cloud9beverages.com/contact", "Cloud9", "Mumbai", "Energy"),
    ("https://hustleenergydrink.com/pages/contactus", "Hustle Energy", "Delhi", "Energy"),
    ("https://www.siporabeverages.com/contact-us.html", "Sipora", "Delhi", "Beverage"),
    ("https://krispywater.com/contact", "Krispy Water", "Ahmedabad", "Hydration"),
    ("https://www.thesouledstore.com/contact-us", "The Souled Store", "Mumbai", "Fashion"),
    ("https://globaltechtrums.com/", "Global Techtrums", "Ahmedabad", "Edtech"),
    ("https://saaras.ai/contact", "Saaras.ai", "Ahmedabad", "Edtech"),
]

# Extra public Gujarat contact guesses scraped from search-style lists (only kept if page confirms email)
GUJARAT_SITE_GUESSES = [
    "https://www.amul.com/m/contact-us",
    "https://www.nid.edu/contact",
    "https://iitgn.ac.in/contact",
    "https://www.nirmauni.ac.in/contact-us/",
    "https://www.daiict.ac.in/contact-us",
    "https://pdpu.ac.in/contact.html",
    "https://www.gujarat.gov.in/contactus",
]


def harvest_page(url: str) -> list[str]:
    try:
        r = httpx.get(url, timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code >= 400:
            return []
        emails = []
        for e in EMAIL_RE.findall(r.text):
            el = e.lower()
            if any(x in el for x in ("example.com", "sentry", "wixpress", "png", "jpg", "godaddy")):
                continue
            if el not in emails and not is_dead(el):
                emails.append(el)
        return emails[:8]
    except Exception:
        return []


def seed_from_existing_packs(conn, sender) -> dict:
    added = queued = 0
    for L in list(LEADS) + list(LOCAL_LEADS):
        email = (L.get("email") or "").strip().lower()
        if not email or is_dead(email):
            continue
        name = L["name"]
        city = L.get("city") or "Ahmedabad"
        cat = L.get("category") or "Brand"
        if upsert_mass_brand(conn, name, email, city, cat, L.get("website") or "", "pack_seed"):
            added += 1
        row = conn.execute("SELECT id FROM brands WHERE lower(contact_email)=?", (email,)).fetchone()
        if row and queue_hard_pitch(conn, row["id"], {"name": name, "contact_email": email, "category": cat}, sender):
            queued += 1
    return {"added": added, "queued": queued}


def seed_from_sites(conn, sender) -> dict:
    added = queued = 0
    for url, name, city, cat in DOMAIN_SEEDS:
        for email in harvest_page(url):
            if upsert_mass_brand(conn, name, email, city, cat, url, "site_scrape"):
                added += 1
            row = conn.execute("SELECT id FROM brands WHERE lower(contact_email)=?", (email,)).fetchone()
            if row and queue_hard_pitch(conn, row["id"], {"name": name, "contact_email": email, "category": cat}, sender):
                queued += 1
    for url in GUJARAT_SITE_GUESSES:
        emails = harvest_page(url)
        for email in emails:
            name = email.split("@")[0].replace(".", " ").title()
            if upsert_mass_brand(conn, name, email, "Ahmedabad", "Gujarat org", url, "site_scrape"):
                added += 1
            row = conn.execute("SELECT id FROM brands WHERE lower(contact_email)=?", (email,)).fetchone()
            if row and queue_hard_pitch(
                conn, row["id"], {"name": name, "contact_email": email, "category": "Gujarat org"}, sender
            ):
                queued += 1
    return {"added": added, "queued": queued}


def expand_via_bing(conn, sender, queries: int = 40) -> dict:
    from agents.mass_brand_hunter import _search, _valid_emails, _guess_city, _guess_category, _brand_name_from_hit

    added = queued = seen = 0
    from agents.mass_brand_hunter import _queries

    for q in _queries(queries):
        for hit in _search(q, 12):
            blob = f"{hit['title']} {hit['snippet']} {hit['url']}"
            emails = _valid_emails(blob)
            if hit["url"].startswith("http"):
                emails = list(dict.fromkeys(emails + harvest_page(hit["url"])))
            for email in emails[:4]:
                seen += 1
                name = _brand_name_from_hit(hit["title"], email)
                city = _guess_city(blob + q)
                cat = _guess_category(blob + q)
                if upsert_mass_brand(conn, name, email, city, cat, hit["url"], q):
                    added += 1
                row = conn.execute("SELECT id FROM brands WHERE lower(contact_email)=?", (email,)).fetchone()
                if row and queue_hard_pitch(
                    conn, row["id"], {"name": name, "contact_email": email, "category": cat}, sender
                ):
                    queued += 1
    return {"added": added, "queued": queued, "emails_seen": seen}


def main():
    init_db()
    ensure_schema()
    sender = sender_profile()
    with get_conn() as conn:
        a = seed_from_existing_packs(conn, sender)
        print("packs", a)
        b = seed_from_sites(conn, sender)
        print("sites", b)
        c = expand_via_bing(conn, sender, queries=60)
        print("bing", c)
        total = conn.execute("SELECT COUNT(*) FROM brands WHERE segment='mass_gujarat'").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM outreach WHERE agent_name='mass_pitch' AND status IN ('draft','approved')"
        ).fetchone()[0]
        print("mass_brands", total, "pending_pitches", pending)


if __name__ == "__main__":
    main()
