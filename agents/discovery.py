"""
Gujarat lead discovery — DuckDuckGo + Allevents calendars + college circuit.

Real event hits are upserted into `events` (not stuck forever in a review queue).
Discoveries still keep a trail for anything that needs a second look.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from agents.sources.allevents import fetch_gujarat as fetch_allevents
from agents.sources.college_circuit import known_gujarat_events
from app.database import get_conn, init_db
from app.services.opportunity import score_opportunity, should_auto_import

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "discovery_config.json"

# Broker marketplaces / junk — NOT public event calendars
BLOCKED_DOMAINS = (
    "sponsorshipsearch.com", "sponsorwale.com", "sponsormyshow.com", "sponsormyevent.com",
    "simplesponsors.com", "sponsoringit.com", "invitemysponsors.com", "barternow.in",
    "scribd.com", "glassdoor", "naukri.com", "indeed.", "quora.com", "reddit.com",
    "hire4event.com", "evepaper.com", "ensun.io", "collegebrandconnect.com",
    "excellentpublicity.com", "wikipedia.org", "youtube.com", "zoominfo.com",
    "justdial.com", "startupgrantsindia.com",
)

# Prefer these when auto-promoting from search
PREFERRED_DOMAINS = (
    "allevents.in", "bookmyshow.com", "meetup.com", "linkedin.com", "instagram.com",
    ".ac.in", ".edu", "iitgn.ac.in", "iima.ac.in", "svnit.ac.in", "daiict.ac.in",
    "nirmauni.ac.in", "pdpu.ac.in", "gtu.ac.in", "charusat.ac.in", "paruluniversity.ac.in",
    "tie.org", "ted.com", "ieeegscon.org", "rushabhayan.org", "vadodaramarathon.com",
)

JUNK_TITLE_MARKERS = (
    "how to find", "how to get", "complete guide", "list of companies", "best sponsorship platforms",
    "what is sponsorship", "jobs near", "hiring", "vacancy", "pdf download", "scheme 202",
    "grant application", "wikipedia", "top college events", "top college fests", "list of all upcoming",
    "events calendar 2026 - allevents", "knowafest", "indcareer", "eventopia", "2026 guide",
    "2026 schedule", "culture & street fairs", "competitions, events contests",
)

CITY_HINTS = (
    ("ahmedabad", "Ahmedabad"), ("surat", "Surat"), ("vadodara", "Vadodara"),
    ("baroda", "Vadodara"), ("rajkot", "Rajkot"), ("gandhinagar", "Gandhinagar"),
    ("bhavnagar", "Bhavnagar"), ("anand", "Anand"), ("mehsana", "Mehsana"),
    ("junagadh", "Junagadh"), ("bharuch", "Bharuch"), ("nadiad", "Anand"),
    ("changa", "Anand"), ("valsad", "Valsad"), ("navsari", "Navsari"),
)

CATEGORY_HINTS = (
    (("marathon", "half marathon", "fun run", "youthrun"), "Marathon / sports"),
    (("tech fest", "hackathon", "robo", "coding", "ingenium", "mindbend", "concours"), "College tech fest"),
    (("cultural", "garba", "sparsh", "chaos", "blithchron", "synapse", "felicity"), "College cultural fest"),
    (("startup", "tiecon", "conference", "summit", "demo day", "networking", "msme", "expo"), "Startup / business conference"),
    (("tedx", "talk", "meetup", "workshop", "concert", "comedy", "exhibition"), "Talk / community event"),
)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"max_results_per_query": 20, "event_queries": [], "brand_queries": [], "auto_promote_events": True}


def _clean_url(href: str) -> str:
    href = href.replace("&amp;", "&")
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) or href
    return href


def _search(query: str, max_results: int) -> list[dict]:
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "in-en"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=25,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return []
    html = resp.text
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div|span)>', html, re.DOTALL)
    results = []
    for i, (href, raw_title) in enumerate(links[:max_results]):
        results.append(
            {
                "title": unescape(re.sub(r"<[^>]+>", "", raw_title)).strip(),
                "url": _clean_url(href),
                "snippet": unescape(re.sub(r"<[^>]+>", "", snippets[i])).strip() if i < len(snippets) else "",
            }
        )
    return results


def is_junk(title: str, url: str) -> bool:
    t, u = title.lower(), url.lower()
    if any(d in u for d in BLOCKED_DOMAINS):
        return True
    return any(m in t for m in JUNK_TITLE_MARKERS)


def _guess_city(text: str, default: str = "Ahmedabad") -> str:
    lower = text.lower()
    for needle, city in CITY_HINTS:
        if needle in lower:
            return city
    return default


def _guess_category(text: str) -> str:
    lower = text.lower()
    for needles, cat in CATEGORY_HINTS:
        if any(n in lower for n in needles):
            return cat
    return "Talk / community event"


def _looks_promotable_event(title: str, url: str, snippet: str) -> bool:
    blob = f"{title} {snippet} {url}".lower()
    if is_junk(title, url):
        return False
    if any(d in url.lower() for d in PREFERRED_DOMAINS):
        return True
    keywords = (
        "fest", "festival", "marathon", "hackathon", "concert", "expo", "exhibition",
        "garba", "summit", "conference", "college", "university", "call for sponsors",
        "seeking sponsors", "navratri", "youth fest", "tech fest",
    )
    return any(k in blob for k in keywords)


def explain(lead_type: str, title: str, snippet: str, query: str) -> str:
    text = f"{title} {snippet}".lower()
    markers = (
        "call for sponsors", "seeking sponsors", "looking for sponsors", "inviting sponsors",
        "sponsorship", "partner with us", "become a sponsor",
    )
    hits = [m for m in markers if m in text]
    if hits:
        return f"Page signals “{hits[0]}” — likely an active {lead_type} opportunity. Query: {query}."
    return f"Possible {lead_type} found via “{query}”. Verify date and contact on the source page."


def _is_unique_event_url(url: str) -> bool:
    u = (url or "").lower()
    # City listing pages are shared by many events — never use them for uniqueness
    if "/e/" in u or "/event/" in u:
        return True
    if "allevents.in" in u and u.rstrip("/").count("/") <= 3:
        return False
    return bool(u) and "allevents.in/" not in u


def _event_exists(conn, name: str, source_url: str = "") -> bool:
    if source_url and _is_unique_event_url(source_url):
        row = conn.execute(
            "SELECT id FROM events WHERE lower(source_url)=? OR lower(website)=?",
            (source_url.lower(), source_url.lower()),
        ).fetchone()
        if row:
            return True
    key = re.sub(r"[^a-z0-9]+", "", name.lower())[:48]
    if not key:
        return False
    rows = conn.execute("SELECT name FROM events").fetchall()
    for r in rows:
        existing = re.sub(r"[^a-z0-9]+", "", (r["name"] or "").lower())[:48]
        if existing and (key == existing or (len(key) > 12 and (key in existing or existing in key))):
            return True
    return False


def upsert_event(conn, item: dict) -> bool:
    name = (item.get("name") or "").strip()
    if not name:
        return False
    source = (item.get("source_url") or item.get("website") or "").strip()
    if _event_exists(conn, name, source):
        return False
    # Smart gate: never import Diljit-scale / directory / no-chance inventory
    if not should_auto_import(item):
        return False
    score, tier, reason = score_opportunity(item)
    discovery_reason = item.get("discovery_reason") or "Imported by Event Scout."
    if reason:
        discovery_reason = f"{discovery_reason} | {reason}"
    conn.execute(
        """
        INSERT INTO events (
            name, city, category, event_date, planning_stage, footfall_estimate,
            organizer_name, organizer_phone, organizer_email, notes,
            description, date_label, audience, contact_role, website, linkedin_url,
            source_url, discovery_reason, opportunity_score, opportunity_tier, opportunity_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name[:200],
            item.get("city") or "Ahmedabad",
            item.get("category") or "Talk / community event",
            item.get("event_date") or "",
            item.get("planning_stage") or "planning",
            int(item.get("footfall_estimate") or 0),
            item.get("organizer_name") or "",
            item.get("organizer_phone") or "",
            item.get("organizer_email") or "",
            item.get("notes") or "",
            item.get("description") or "",
            item.get("date_label") or "",
            item.get("audience") or "",
            item.get("contact_role") or "",
            item.get("website") or source,
            item.get("linkedin_url") or "",
            source,
            discovery_reason[:500],
            score,
            tier,
            reason[:500],
        ),
    )
    return True


def _queue_discovery(conn, lead_type: str, title: str, snippet: str, url: str, query: str) -> bool:
    if not url:
        return False
    if conn.execute("SELECT 1 FROM discoveries WHERE source_url=?", (url,)).fetchone():
        return False
    conn.execute(
        """
        INSERT INTO discoveries (lead_type, title, snippet, source_url, query_used, why_chosen, status)
        VALUES (?, ?, ?, ?, ?, ?, 'candidate')
        """,
        (lead_type, title[:250], snippet[:600], url, query, explain(lead_type, title, snippet, query)),
    )
    return True


def seed_college_circuit(conn) -> int:
    added = 0
    for item in known_gujarat_events():
        if upsert_event(conn, item):
            added += 1
    return added


def import_allevents(conn, limit_per_city: int = 30) -> int:
    added = 0
    for item in fetch_allevents(limit_per_city=limit_per_city):
        if upsert_event(conn, item):
            added += 1
            _queue_discovery(
                conn,
                "event",
                item["name"],
                item.get("discovery_reason", ""),
                item.get("source_url", ""),
                "allevents calendar",
            )
    return added


ProgressFn = Callable[..., None]


def run_discovery(progress: ProgressFn | None = None) -> dict:
    def emit(message: str, **meta) -> None:
        if progress:
            try:
                progress(message, **meta)
            except Exception:
                pass

    init_db()
    cfg = load_config()
    max_r = int(cfg.get("max_results_per_query", 20))
    auto_promote = bool(cfg.get("auto_promote_events", True))
    stats = {
        "queries": 0,
        "candidates": 0,
        "rejected": 0,
        "events_added": 0,
        "college_seeded": 0,
        "allevents_added": 0,
    }
    jobs = [("event", q) for q in cfg.get("event_queries", [])] + [
        ("brand", q) for q in cfg.get("brand_queries", [])
    ]

    with get_conn() as conn:
        emit("Seeding known Gujarat college circuit events…", agent="Event Scout", phase="scanning")
        stats["college_seeded"] = seed_college_circuit(conn)
        stats["events_added"] += stats["college_seeded"]
        if stats["college_seeded"]:
            emit(
                f"College circuit added {stats['college_seeded']} new event(s)",
                agent="Event Scout",
                level="success",
                phase="scanning",
            )

        emit("Pulling Allevents Gujarat calendars…", agent="Event Scout", phase="scanning")
        try:
            stats["allevents_added"] = import_allevents(conn)
            stats["events_added"] += stats["allevents_added"]
            emit(
                f"Allevents imported {stats['allevents_added']} new event(s)",
                agent="Event Scout",
                level="success" if stats["allevents_added"] else "info",
                phase="scanning",
            )
        except Exception as exc:
            stats["allevents_error"] = str(exc)[:200]
            emit(
                f"Allevents scan failed: {exc}",
                agent="Event Scout",
                level="warn",
                phase="scanning",
            )

        total_jobs = len(jobs)
        for idx, (lead_type, query) in enumerate(jobs, start=1):
            stats["queries"] += 1
            agent = "Brand Scout" if lead_type == "brand" else "Event Scout"
            emit(
                f"Searching web ({idx}/{total_jobs}): {query}",
                agent=agent,
                detail=f"Looking for {lead_type} leads",
                phase="scanning",
                query=query,
            )
            hits = _search(query, max_r)
            found_here = 0
            imported_here = 0
            for hit in hits:
                if not hit["url"] or is_junk(hit["title"], hit["url"]):
                    stats["rejected"] += 1
                    continue
                queued = _queue_discovery(conn, lead_type, hit["title"], hit["snippet"], hit["url"], query)
                if queued:
                    stats["candidates"] += 1
                    found_here += 1
                if (
                    auto_promote
                    and lead_type == "event"
                    and _looks_promotable_event(hit["title"], hit["url"], hit["snippet"])
                ):
                    item = {
                        "name": hit["title"][:180],
                        "city": _guess_city(f"{hit['title']} {hit['snippet']} {query}"),
                        "category": _guess_category(f"{hit['title']} {hit['snippet']}"),
                        "source_url": hit["url"],
                        "website": hit["url"],
                        "planning_stage": "seeking_sponsors",
                        "discovery_reason": explain("event", hit["title"], hit["snippet"], query),
                        "notes": "Auto-promoted from web discovery. Verify organizer contact before outreach.",
                        "date_label": "Verify on source page",
                        "description": hit["snippet"][:400],
                    }
                    if upsert_event(conn, item):
                        stats["events_added"] += 1
                        imported_here += 1
                        if queued or True:
                            conn.execute(
                                "UPDATE discoveries SET status='imported', imported_table='events' "
                                "WHERE source_url=? AND status='candidate'",
                                (hit["url"],),
                            )
            if found_here or imported_here:
                emit(
                    f"Query done — {found_here} candidate(s), {imported_here} event(s) imported",
                    agent=agent,
                    level="success",
                    detail=query,
                    phase="scanning",
                )

    return stats


def migrate() -> None:
    init_db()
