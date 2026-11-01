"""Private fit scoring between one event and one brand, with a plain-English reason."""

from datetime import date

CATEGORIES = [
    "College cultural fest",
    "College tech fest",
    "Marathon / sports",
    "Startup / business conference",
    "Talk / community event",
]

GUJARAT_CITIES = ("ahmedabad", "gandhinagar", "vadodara", "surat", "rajkot", "gujarat")


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _days_until(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return (date.fromisoformat(iso[:10]) - date.today()).days
    except ValueError:
        return None


def _region(city: str) -> str:
    c = (city or "").lower()
    if "pan-india" in c or "india" == c.strip():
        return "pan-india"
    if any(g in c for g in GUJARAT_CITIES):
        return "gujarat"
    return c


def score_match(event: dict, brand: dict) -> tuple[float, str, str]:
    score = 0.0
    reasons: list[str] = []

    category = (event.get("category") or "").strip()
    targets = _split(brand.get("target_categories"))
    category_fit = bool(category) and category in targets
    if category_fit:
        score += 45
        reasons.append(f"a {category.lower()} is the kind of event {brand.get('name')} fits")

    e_city = (event.get("city") or "").split(",")[0].strip()
    e_region, b_region = _region(event.get("city", "")), _region(brand.get("city", ""))
    if b_region == "pan-india":
        score += 15
        reasons.append("national brand that sponsors campus events across India")
    elif e_city and e_city.lower() in (brand.get("city") or "").lower():
        score += 25
        reasons.append(f"both based in {e_city}")
    elif e_region == b_region == "gujarat":
        score += 20
        reasons.append("both in Gujarat")

    footfall = int(event.get("footfall_estimate") or 0)
    if footfall >= 10000:
        score += 15
        reasons.append(f"{footfall:,}+ attendees — big reach")
    elif footfall >= 2000:
        score += 10
        reasons.append(f"{footfall:,}+ attendees")
    elif footfall:
        score += 4

    days = _days_until(event.get("event_date"))
    if days is not None:
        if 30 <= days <= 150:
            score += 15
            reasons.append(f"event in ~{days // 30 or 1} month(s) — sponsors are being signed now")
        elif 150 < days <= 240:
            score += 8
            reasons.append("event 5–8 months away — early, good time to reserve")
        elif 0 <= days < 30:
            score += 2
            reasons.append("event very soon — only small slots likely")
        elif days < 0:
            score -= 30
            reasons.append("event date has passed")

    score = max(0.0, min(100.0, score))
    if not category_fit:
        score = min(score, 40.0)
        reasons.insert(0, "event type is outside what this brand sponsors")
    if score >= 80:
        tier = "excellent"
    elif score >= 65:
        tier = "strong"
    elif score >= 50:
        tier = "possible"
    else:
        tier = "weak"

    reason = "; ".join(reasons) if reasons else "Low overlap"
    return score, tier, reason[0].upper() + reason[1:]
