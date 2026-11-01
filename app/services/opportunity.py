"""Score whether an event is worth chasing for a small Gujarat sponsorship broker.

Goal: only surface inventory where (1) we can actually reach the organizer,
(2) sponsor packages are still being sold / will open, and (3) giants/agencies
have not already locked the market (celebrity India tours, etc.).
"""

from __future__ import annotations

import re
from datetime import date

# National / celebrity inventory — BookMyShow, DMI, big agencies own these.
MEGA_ARTIST_MARKERS = (
    "diljit", "dosanjh", "arijit", "badshah", "apun", "papon", "darshan raval",
    "sachin & jigar", "sachin and jigar", "apna bana le", "lakhwinder wadali",
    "manhar udhas", "neha kakkar", "shreya ghoshal", "sonu nigam", "kk live",
    "sunburn", "tomorrowland", "coldplay", "ed sheeran", "aura india tour",
    "india tour-onelife", "india tour", "bangtanverse", "bts carnival",
    "karunesh talwar", "osho jain", "rahul subramanian", "zakir khan",
    "biswa kalyan", "anubhav singh bassi", "gaurav kapoor", "rajat sood",
)

# Aggregator / directory *titles* — not real chaseable events (check name, not source URL)
DIRECTORY_TITLE_MARKERS = (
    "events & things to do", "monthly calendar", "upcoming events in",
    "all events in", "festivals, concerts, melas", "events & happenings",
    "explore local events", "events diary", "festival calendar in",
    "list of all", "top college events", "top festivals", "things to do in",
    "dates & tickets", "kundlit", "eventopia", "knowafest", "indcareer",
    "upcoming & ongoing expos", "exhibitions in gandhinagar 2026",
    "upcoming conferences events", "environment conferences", "social conferences",
    "best live events", "best festivals in", "events calendar 2026",
    "conferences in surat -", "events - electronics for you", "official site electronics",
    "| allevents", "allevents.in/",  # only when the *title* is the city feed
)

# Tiny / non-commercial — not worth brokerage time
# (Do NOT use bare "workshop" — college tech fests mention workshops in copy.)
TOO_SMALL_MARKERS = (
    "open mic", "book club", "paint play", "workshop for chocolate", "snorkelling",
    "star gazing", "halloween party", "kids art", "clay trinket", "terrarium",
    "stone painting", "foil art", "kintsugi", "perfumery", "yoga class",
    "inter church", "freedom cup", "art date", "trinket tray",
)

# Signals that packages are still open (history: orgs that publish these convert)
OPEN_WINDOW_MARKERS = (
    "call for sponsors", "seeking sponsors", "looking for sponsors",
    "sponsorship enquir", "sponsorship inquir", "become a sponsor",
    "partner with us", "sponsorship opportunit", "for sponsorship",
    "sponsor packages", "title sponsor", "stall sponsor", "invite sponsors",
)

# Categories a solo Gujarat broker historically closes with SMEs / edtech / local banks
BROKER_FIT_CATEGORIES = {
    "College cultural fest": 35,
    "College tech fest": 38,
    "Marathon / sports": 32,
    "Startup / business conference": 28,
    "Talk / community event": 8,
}

# Past-sponsor proof in copy (shows appetite; associate/stall often still open)
HISTORY_SPONSOR_MARKERS = (
    "past sponsors", "past partners", "previous sponsors", "title)", "campa",
    "bank of baroda", "sbi", "boeing", "reliance", "adani", "tata", "itc",
    "ibm", "drdo",
)


def _blob(event: dict) -> str:
    parts = [
        event.get("name"),
        event.get("description"),
        event.get("discovery_reason"),
        event.get("notes"),
        event.get("audience"),
        event.get("contact_role"),
        event.get("category"),
        event.get("source_url"),
        event.get("website"),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def _days_until(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return (date.fromisoformat(str(iso)[:10]) - date.today()).days
    except ValueError:
        return None


def _has_reach(event: dict) -> bool:
    return bool(
        (event.get("organizer_email") or "").strip()
        or (event.get("organizer_phone") or "").strip()
        or (event.get("linkedin_url") or "").strip()
        or (event.get("website") or "").strip()
        or (event.get("source_url") or "").strip()
    )


def score_opportunity(event: dict) -> tuple[float, str, str]:
    """Return (score 0–100, tier chase|research|skip, plain-English reason)."""
    blob = _blob(event)
    name = (event.get("name") or "").lower()
    reasons: list[str] = []

    # --- Hard skips ---
    if (
        any(m in name for m in DIRECTORY_TITLE_MARKERS)
        or name.startswith("events &")
        or "things to do" in name
        or name.strip().endswith("| allevents")
        or re.search(r"^events?\s+in\s+\w+", name)
    ):
        return 5.0, "skip", "Directory / calendar page — not a single chaseable organizer."

    if any(m in blob for m in MEGA_ARTIST_MARKERS):
        return 3.0, "skip", (
            "Celebrity / national tour inventory. Giants and agencies already lock these — "
            "not a realistic win for a local brokerage."
        )

    if any(m in name for m in TOO_SMALL_MARKERS) or any(m in blob for m in TOO_SMALL_MARKERS):
        return 8.0, "skip", "Too small / social — no real sponsorship package to sell."

    # Wrong geography noise
    if "foshan" in blob or "tanzhou" in blob:
        return 2.0, "skip", "Not a Gujarat venue — listing noise."

    # Stand-alone ticketed comedy of touring comics (low organizer access)
    if ("standup" in blob or "stand-up" in blob or "comedy show" in blob) and "college" not in blob:
        if any(x in blob for x in ("amit khuva", "inder sahani", "avinash agarwal", "mamooli")):
            return 12.0, "skip", "Touring standup — ticketed show, sponsor desk usually closed or agency-held."

    score = 20.0  # base for surviving hard filters
    category = (event.get("category") or "").strip()
    score += BROKER_FIT_CATEGORIES.get(category, 5)
    if category in BROKER_FIT_CATEGORIES and category != "Talk / community event":
        reasons.append(f"{category} is inventory SMEs/edtech historically buy in Gujarat")

    # Open sponsor window signals
    if any(m in blob for m in OPEN_WINDOW_MARKERS):
        score += 28
        reasons.append("public ‘call for sponsors’ / package language — booking window looks open")
    if (event.get("organizer_email") or "").lower().startswith("sponsor") or "sponsor@" in (
        event.get("organizer_email") or ""
    ).lower():
        score += 18
        reasons.append("dedicated sponsorship inbox — they are set up to take brand deals")
    elif "@" in (event.get("organizer_email") or ""):
        score += 10
        reasons.append("public organizer email — reachable without a gatekeeper agency")

    if (event.get("planning_stage") or "") in ("seeking_sponsors", "packages_open"):
        score += 12
        reasons.append("marked seeking sponsors / packages open")

    # History: past sponsors prove demand; leave room for associate/stall
    if any(m in blob for m in HISTORY_SPONSOR_MARKERS):
        score += 10
        reasons.append("past-sponsor history — demand proven; chase associate / stall / co-present, not only title")

    # Timing: sweet spot 45–180 days for campus / marathon closes
    days = _days_until(event.get("event_date"))
    if days is not None:
        if 45 <= days <= 180:
            score += 14
            reasons.append(f"~{days} days out — typical signing window for Gujarat campus/sports deals")
        elif 20 <= days < 45:
            score += 6
            reasons.append("close-in — only chase if packages still open")
        elif days < 20:
            score -= 15
            reasons.append("too close to event date — inventory usually sold")
        elif 180 < days <= 300:
            score += 8
            reasons.append("early — good time to reserve before agencies fill the book")

    # Footfall band that converts for local brands (not stadium 50k+ celebrity)
    footfall = int(event.get("footfall_estimate") or 0)
    if 1500 <= footfall <= 40000:
        score += 10
        reasons.append(f"~{footfall:,} footfall — right size for local/SME packages")
    elif footfall > 80000 and any(m in blob for m in MEGA_ARTIST_MARKERS):
        score -= 20

    # Mid-size B2B expos / lit fests / city runs — historically sell stalls late
    if any(
        x in blob
        for x in (
            "expo", "exhibition", "trade show", "engitech", "engiexpo", "efy",
            "dairy world", "litfest", "lit fest", "marathon", "youthrun", "fun run",
            "machine tools", "msme", "startup demo", "networking", "hackathon",
            "college fest", "tech fest", "cultural fest",
        )
    ):
        score += 8
        if "expo" in blob or "exhibition" in blob:
            reasons.append("B2B/expo-style inventory — stalls often still available closer to date")

    # Reachability
    if not _has_reach(event):
        score -= 10
        reasons.append("no public reach channel yet — research contact before pitching")
    elif not (event.get("organizer_email") or event.get("organizer_phone")):
        score -= 3
        reasons.append("website/LinkedIn only — find a name before Send All")

    # Vibrant Gujarat / state mega — hard for solo broker unless side event
    if "vibrant gujarat" in blob and "side" not in blob:
        score -= 12
        reasons.append("state mega-summit — main book is agency/gov locked; only chase side events")

    # National medical / association congresses — sponsor book locked years ahead by agencies
    if any(x in blob for x in ("dermacon", "national conference of ia", "iapsmgc")):
        score -= 25
        reasons.append("national association congress — title inventory usually pre-booked by agencies")

    # Soft demote lifestyle shopping carnivals / generic art weeks (stall-only, low fee)
    if any(x in name for x in ("fashion mantra", "jalsa diwali", "artrest", "hi life", "black dot")):
        score -= 15
        reasons.append("lifestyle exhibition — low package value unless you already have retail brands")

    score = max(0.0, min(100.0, score))

    if score >= 55:
        tier = "chase"
    elif score >= 35:
        tier = "research"
    else:
        tier = "skip"

    if not reasons:
        reasons.append("Weak sponsor-window signals — verify before spending outreach time.")

    # Prefer the highest-signal reasons first
    reason = "; ".join(reasons[:3])
    if tier == "chase":
        reason = "CHASE — " + reason
    elif tier == "research":
        reason = "RESEARCH — " + reason
    else:
        reason = "SKIP — " + reason
    return score, tier, reason


def rescore_all_events(conn) -> dict:
    """Write opportunity_* fields on every event. Returns counts by tier."""
    rows = conn.execute("SELECT * FROM events").fetchall()
    counts = {"chase": 0, "research": 0, "skip": 0}
    for row in rows:
        e = dict(row)
        score, tier, reason = score_opportunity(e)
        counts[tier] = counts.get(tier, 0) + 1
        conn.execute(
            """
            UPDATE events
            SET opportunity_score=?, opportunity_tier=?, opportunity_reason=?
            WHERE id=?
            """,
            (score, tier, reason, e["id"]),
        )
    return counts


def should_auto_import(event_like: dict) -> bool:
    """Gate for discovery/Allevents — only import chase or research."""
    _, tier, _ = score_opportunity(event_like)
    return tier in ("chase", "research")
