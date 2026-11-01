"""Pull upcoming public listings from Allevents for Gujarat cities."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

import httpx

CITIES = (
    ("ahmedabad", "Ahmedabad"),
    ("surat", "Surat"),
    ("vadodara", "Vadodara"),
    ("rajkot", "Rajkot"),
    ("gandhinagar", "Gandhinagar"),
    ("bhavnagar", "Bhavnagar"),
    ("anand", "Anand"),
    ("mehsana", "Mehsana"),
    ("junagadh", "Junagadh"),
    ("bharuch", "Bharuch"),
)

# Tiny / non-sponsorable / agency-locked celebrity noise
SKIP_TITLE = (
    "open mic", "book club", "paint play", "workshop for chocolate", "snorkelling",
    "star gazing", "puzzle of jokes", "halloween party", "live screening", "el clasico",
    "barcelona vs", "real madrid", "movie", "film screening", "yoga class",
    "diljit", "dosanjh", "arijit", "papon", "darshan raval", "sachin & jigar",
    "apna bana le", "lakhwinder", "manhar udhas", "bangtanverse", "karunesh talwar",
    "osho jain", "rahul subramanian", "zakir khan", "gaurav kapoor", "rajat sood",
    "amit khuva", "inder sahani", "namaste trump", "daru badnaam",
)

SPONSORABLE_HINTS = (
    "fest", "festival", "concert", "marathon", "run", "expo", "exhibition", "hackathon",
    "conference", "summit", "networking", "startup", "msme", "tour", "carnival",
    "garba", "cultural", "tech", "comedy", "live in", "india tour", "bazaar", "mela",
    "symposium", "conclave", "trade show", "business", "litfest", "lit fest", "standup",
    "stand-up", "demo day", "engiexpo", "hi life",
)


def _guess_category(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ("marathon", "run for", "fun run", "youthrun")):
        return "Marathon / sports"
    if any(x in t for x in ("hackathon", "tech fest", "ingenium", "expo", "engitech")):
        return "College tech fest"
    if any(x in t for x in ("garba", "cultural", "fest", "carnival")):
        return "College cultural fest"
    if any(x in t for x in ("startup", "msme", "networking", "conference", "summit", "demo day")):
        return "Startup / business conference"
    if any(x in t for x in ("concert", "live in", "tour", "qawwali", "comedy")):
        return "Talk / community event"
    if "exhibition" in t or "bazaar" in t or "mela" in t:
        return "Talk / community event"
    return "Talk / community event"


def _is_useful(title: str) -> bool:
    t = title.lower().strip()
    if len(t) < 6:
        return False
    if any(s in t for s in SKIP_TITLE):
        return False
    return any(h in t for h in SPONSORABLE_HINTS)


def fetch_city(slug: str, city_label: str, limit: int = 40) -> list[dict]:
    url = f"https://allevents.in/{slug}/all"
    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return []

    html = resp.text
    # Event cards / links: /e/<slug>-<id> or similar
    pattern = re.compile(
        r'href="(https?://allevents\.in/e/[^"]+|/[a-z0-9\-]+/e/[a-z0-9\-]+)"[^>]*>\s*'
        r"(?:<[^>]+>\s*)*([^<]{6,160})",
        re.I,
    )
    found: list[dict] = []
    seen: set[str] = set()
    for href, raw_title in pattern.findall(html):
        title = unescape(re.sub(r"\s+", " ", raw_title)).strip()
        if not _is_useful(title):
            continue
        full = href if href.startswith("http") else urljoin("https://allevents.in", href)
        key = full.split("?")[0].lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(
            {
                "name": title[:180],
                "city": city_label,
                "category": _guess_category(title),
                "source_url": full,
                "website": full,
                "planning_stage": "seeking_sponsors",
                "discovery_reason": f"Listed on Allevents ({city_label}) — public upcoming event calendar.",
                "date_label": "See Allevents listing for date",
                "notes": "Auto-imported from Allevents. Verify date, organizer contact, and sponsor openness.",
            }
        )
        if len(found) >= limit:
            break

    # Fallback: JSON-ish / title blocks if link regex misses
    if len(found) < 5:
        titles = re.findall(r"<h3[^>]*>([^<]{8,120})</h3>", html, re.I)
        for raw in titles:
            title = unescape(re.sub(r"\s+", " ", raw)).strip()
            if not _is_useful(title):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "name": title[:180],
                    "city": city_label,
                    "category": _guess_category(title),
                    "source_url": url,
                    "website": url,
                    "planning_stage": "seeking_sponsors",
                    "discovery_reason": f"Listed on Allevents city page ({city_label}).",
                    "date_label": "See Allevents listing for date",
                    "notes": "Auto-imported from Allevents city feed. Open the city page to find the exact event link and organizer.",
                }
            )
            if len(found) >= limit:
                break
    return found


def fetch_gujarat(limit_per_city: int = 35) -> list[dict]:
    out: list[dict] = []
    seen_names: set[str] = set()
    for slug, label in CITIES:
        for item in fetch_city(slug, label, limit=limit_per_city):
            key = re.sub(r"[^a-z0-9]+", "", item["name"].lower())[:60]
            if key in seen_names:
                continue
            seen_names.add(key)
            out.append(item)
    return out
