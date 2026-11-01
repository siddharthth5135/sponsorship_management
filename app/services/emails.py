"""Outreach copy for organizers and brands.

Organizer email: one goal — get their sponsorship deck and permission to sell open slots.
Brand email: one goal — learn whether they sponsor events in the next 3–6 months, and who decides.
"""

import json
from urllib.parse import quote

from app.paths import sender_profile_path

PROFILE_PATH = sender_profile_path()

# Official Blithchron '27 sponsorship brochure (Drive)
BLITHCHRON_BROCHURE_URL = (
    "https://drive.google.com/file/d/1krYH0O00IcL654k4cNzImwliUc2oGPKO/view"
)


FIT_LINES = {
    "College cultural fest": {
        "sampling": "a sampling counter puts your product in thousands of students' hands in one weekend",
        "leads": "a branded competition or stall drives sign-ups from students across colleges",
        "awareness": "stage, concert and social-media branding in front of a young, high-energy crowd",
    },
    "College tech fest": {
        "sampling": "an energy partner for hackathons and competitions, where students are there for hours",
        "leads": "hosting a hackathon or coding challenge brings direct sign-ups from engineering students",
        "awareness": "brand presence with India's future engineers and tech talent",
    },
    "Marathon / sports": {
        "sampling": "a hydration or energy counter on the route and at the finish puts product in every runner's hand",
        "leads": "race-kit inserts and on-ground activations reach health-conscious families",
        "awareness": "branding on bibs, the start line and race-day media across the city",
    },
    "Startup / business conference": {
        "sampling": "refreshments partner for Gujarat's founders, investors and business owners",
        "leads": "a stall and speaking slot in front of founders and decision-makers",
        "awareness": "visibility with Gujarat's business community and leadership",
    },
    "Talk / community event": {
        "sampling": "official refreshments partner for a smaller, premium audience",
        "leads": "a curated, engaged audience of students and young professionals",
        "awareness": "logo on stage and in every talk video published online",
    },
}


def _fit_line(event: dict, goal: str) -> str:
    lines = FIT_LINES.get(event.get("category") or "", {})
    return lines.get(goal) or lines.get("awareness") or "a good audience match for your brand"


def sender_profile() -> dict:
    path = sender_profile_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"name": "Siddharth Patel", "title": "", "email": "siddharththpatel@gmail.com", "phone": ""}


def _signature(sender: dict) -> str:
    lines = ["Best regards,", sender["name"]]
    if sender.get("title"):
        lines.append(sender["title"])
    lines.append(sender["email"])
    if sender.get("phone"):
        lines.append(sender["phone"])
    return "\n".join(lines)


def _first_name(contact_name: str | None) -> str | None:
    name = (contact_name or "").strip()
    if not name or any(w in name.lower() for w in ("team", "committee", "office", "cell")):
        return None
    return name.split()[0]


def _short_event_name(name: str) -> str:
    for sep in (" — ", " - ", " | "):
        if sep in name:
            return name.split(sep)[0].strip()
    return name.strip()


def organizer_email(event: dict, sender: dict | None = None) -> tuple[str, str]:
    sender = sender or sender_profile()
    short = _short_event_name(event["name"])
    first = _first_name(event.get("organizer_name"))
    greeting = f"Hi {first}," if first else f"Hi {short} team,"
    audience = event.get("audience") or "your attendees"

    if event.get("planning_stage") in ("seeking_sponsors", "packages_open", "advertised_locked"):
        opener = f"I saw that {short} is looking for sponsors, and I'd like to help you fill the slots that are still open."
        subject = f"Filling the open sponsor slots at {short}"
    else:
        opener = f"I'm reaching out early, while sponsorship for {short} is still being planned, because I'd like to help you sign sponsors for it."
        subject = f"Signing sponsors for {short} — no upfront cost"
    body = f"""{greeting}

{opener}

I work with brands that sponsor events in Gujarat — food and beverage, student platforms and consumer brands that want to reach {audience}.

How it works:
• I shortlist brands that fit your audience and pitch them on your behalf.
• You approve every brand before I contact them.
• No retainer, nothing upfront. My fee is a nominal conversion fee for facilitating the sponsorship, payable only after you receive the payment from the sponsor.

To get started I only need two things:
1. Your sponsorship deck or tier list with prices
2. Which slots are still open

Could we speak for 15 minutes this week? If that's easier, just reply with the deck and I'll send you a shortlist of brands I would approach within 48 hours.

{_signature(sender)}"""
    return subject, body


def brand_email(brand: dict, events: list[dict] | None = None, sender: dict | None = None) -> tuple[str, str]:
    """Brand pitch only: short, free for the brand, 1–2 questions, ask for a meeting."""
    sender = sender or sender_profile()
    first = _first_name(brand.get("contact_name"))
    greeting = f"Hi {first}," if first else f"Hi {brand['name']} team,"
    segment = (brand.get("segment") or brand.get("category") or "your category").lower()

    subject = f"{brand['name']} × Gujarat campus events — no fee from your side"
    body = f"""{greeting}

I'm {sender['name'].split()[0]}. Our team works with college and youth-event organizers in Gujarat and helps brands get sponsorships at a fair, negotiable rate.

For brands there is no charge from us — no brokerage, no retainer, nothing to start. You only pay the event for the package you approve.

We shortlist events that fit {segment}, share honest rates, and our team coordinates with the organizer so you only decide yes or no.

Quick question: would that be useful for {brand['name']} in the next few months? If yes, who should we speak with for a 15-minute call this week?

Reply with a time (or WhatsApp number) and we’ll lock it in.

{_signature(sender)}"""
    return subject, body


def blithchron_brand_email(brand: dict, sender: dict | None = None) -> tuple[str, str]:
    """Dedicated Blithchron '27 pitch — one event, clear package ask."""
    sender = sender or sender_profile()
    first = _first_name(brand.get("contact_name"))
    greeting = f"Hi {first}," if first else f"Hi {brand.get('name', 'there')} team,"
    package = brand.get("package") or "Associate / Event Sponsor"
    ask = brand.get("ask_inr") or "a flexible package"
    pitch = brand.get("pitch") or "youth cultural audience at IIT Gandhinagar"
    name = brand.get("name") or "your brand"

    subject = f"{name} × Blithchron '27 IIT Gandhinagar (4–7 Feb) — {package}"
    body = f"""{greeting}

I'm {sender['name'].split()[0]}. I'm working with Blithchron '27 — IIT Gandhinagar's annual cultural fest (4–7 February 2027).

Quick facts: ~22,000 footfall, two Pronites (6,000+ per night), 100+ partner colleges across Gujarat. Past associates include Central Bank of India (Title '25), Coca-Cola, Monster, Maggi and The Souled Store.

Official sponsorship brochure (tiers, deliverables, past sponsors):
{BLITHCHRON_BROCHURE_URL}

For {name} we're proposing: {package} (indicative band {ask}). {pitch}

For brands there is no fee from our side — you only pay the fest for the package you approve. Category exclusivity is available on a first-come basis for Energy / Beverage / Hydration / Banking.

Could we do a 15-minute call this week after you've glanced at the brochure? Or reply with the right person for campus / brand partnerships.

{_signature(sender)}"""
    return subject, body


def blithchron_brochure_email(brand: dict, sender: dict | None = None) -> tuple[str, str]:
    """Short share of the official brochure — for everyone, including prior pitches."""
    sender = sender or sender_profile()
    first = _first_name(brand.get("contact_name"))
    name = brand.get("name") or "your brand"
    greeting = f"Hi {first}," if first else f"Hi {name} team,"
    subject = f"Blithchron '27 sponsorship brochure — IIT Gandhinagar (4–7 Feb)"
    body = f"""{greeting}

Sharing the official Blithchron '27 sponsorship brochure so you have a clear picture of the fest, packages, deliverables and past sponsors:

{BLITHCHRON_BROCHURE_URL}

Blithchron is IIT Gandhinagar's annual cultural fest (4–7 February 2027) — ~22,000 footfall, two Pronites. From the brand side there is no brokerage fee; you only pay the fest for the package you approve.

Happy to walk you through a fit for {name} on a 10-minute call after you've opened the PDF.

{_signature(sender)}"""
    return subject, body


def gmail_compose_url(to_email: str, subject: str, body: str, from_email: str) -> str:
    return (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&authuser={quote(from_email)}"
        f"&to={quote(to_email or '')}"
        f"&su={quote(subject or '')}"
        f"&body={quote(body or '')}"
    )
