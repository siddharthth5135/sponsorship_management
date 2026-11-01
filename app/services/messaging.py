"""One-click outreach links: WhatsApp, SMS, LinkedIn search, copyable pitch."""

from __future__ import annotations

from urllib.parse import quote


BROCHURE_URL = "https://drive.google.com/file/d/1krYH0O00IcL654k4cNzImwliUc2oGPKO/view"

PITCH_TEMPLATE = (
    "Hi, I'm reaching out about Blithchron '27 — IIT Gandhinagar's annual cultural fest "
    "(4–7 Feb 2027). ~22,000 footfall, two Pronites with 6,000+ a night, 100+ partner colleges. "
    "Past associates include CBI, Coca-Cola, Monster, Maggi. "
    "Official brochure: {brochure} "
    "For {brand} we're proposing {package} (around {ask}). "
    "No fee from our side — you only pay the fest for the package you approve. "
    "Category exclusivity available first-come. Can we do a 10-min call this week?"
)


def pitch_text(brand: dict) -> str:
    return PITCH_TEMPLATE.format(
        brand=brand.get("name") or "your brand",
        package=brand.get("package") or brand.get("category") or "Associate / stall partner",
        ask=brand.get("ask_inr") or brand.get("ask") or "a flexible local package",
        brochure=BROCHURE_URL,
    )


def phone_to_wa(phone: str | None) -> str | None:
    """Return WhatsApp digits (91XXXXXXXXXX) or None if not usable."""
    if not phone:
        return None
    # Prefer first chunk that looks like a mobile
    chunks = phone.replace(";", "/").replace(",", "/").split("/")
    for chunk in chunks:
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            continue
        if digits.startswith("91") and len(digits) >= 12:
            return digits[:12]
        if len(digits) == 10 and digits[0] in "6789":
            return "91" + digits
        if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
            return "91" + digits[1:]
        # Gujarat landline 79xxxxxxxx → still open WhatsApp if business uses it on WA
        if len(digits) == 10:
            return "91" + digits
        if len(digits) >= 10:
            last10 = digits[-10:]
            if last10[0] in "6789" or last10.startswith("79"):
                return "91" + last10
    return None


def whatsapp_url(phone: str | None, text: str) -> str | None:
    wa = phone_to_wa(phone)
    if not wa:
        return None
    return f"https://wa.me/{wa}?text={quote(text)}"


def sms_url(phone: str | None, text: str) -> str | None:
    wa = phone_to_wa(phone)
    if not wa:
        return None
    # sms: works on mobile; body param varies by OS — use common form
    return f"sms:+{wa}?&body={quote(text)}"


def linkedin_search_url(brand_name: str, role_hint: str = "marketing OR brand OR partnerships") -> str:
    q = f"{brand_name} {role_hint} India"
    return f"https://www.linkedin.com/search/results/all/?keywords={quote(q)}"


def linkedin_company_search_url(brand_name: str) -> str:
    return f"https://www.linkedin.com/search/results/companies/?keywords={quote(brand_name)}"


def enrich_channels(brand: dict) -> dict:
    """Attach wa_url, sms_url, linkedin_url, pitch for templates."""
    text = pitch_text(brand)
    phone = brand.get("contact_phone") or brand.get("phone") or ""
    return {
        "pitch": text,
        "wa_url": whatsapp_url(phone, text),
        "sms_url": sms_url(phone, text),
        "linkedin_people": linkedin_search_url(brand.get("name") or ""),
        "linkedin_company": linkedin_company_search_url(brand.get("name") or ""),
        "has_wa": bool(phone_to_wa(phone)),
        "has_email": bool((brand.get("contact_email") or brand.get("email") or "").strip()),
    }
