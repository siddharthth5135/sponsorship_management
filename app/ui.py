"""Display helpers for templates."""

STAGE_LABELS = {
    "planning": "Planning",
    "seeking_sponsors": "Seeking sponsors",
    "packages_open": "Packages open",
    "advertised_locked": "Late / limited slots",
}

STAGE_TONE = {
    "planning": "neutral",
    "seeking_sponsors": "info",
    "packages_open": "ok",
    "advertised_locked": "warn",
}

NOISY_TITLE_MARKERS = (
    "top indian companies",
    "pdf",
    "quora",
    "how to",
    "list of",
    "sponsor united",
    "what is",
    "blog",
)


def stage_label(code: str) -> str:
    return STAGE_LABELS.get(code or "", (code or "Unknown").replace("_", " ").title())


def stage_tone(code: str) -> str:
    return STAGE_TONE.get(code or "", "neutral")


def why_summary(text: str | None) -> str:
    if not text:
        return "Added manually by your team"
    t = text.strip()
    if t.startswith("Matched event query") or t.startswith("Matched brand query"):
        return "Agent found via web search — please verify"
    if "Public call" in t or "research_import" in t.lower():
        return "Verified public call for sponsors"
    if len(t) > 90:
        return t[:87] + "…"
    return t


def lead_quality(name: str, discovery_reason: str | None = None, notes: str | None = None) -> str:
    """verified | review | manual"""
    n = (name or "").lower()
    if any(m in n for m in NOISY_TITLE_MARKERS):
        return "review"
    if notes and notes.startswith("Verified"):
        return "verified"
    if discovery_reason and (
        "research_import" in discovery_reason or "Public call" in discovery_reason
    ):
        return "verified"
    if discovery_reason and discovery_reason.startswith("Matched"):
        return "review"
    if not discovery_reason:
        return "manual"
    return "review"


def quality_label(q: str) -> str:
    return {"verified": "Verified lead", "review": "Needs review", "manual": "Manual"}.get(q, q)


def split_csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def tel_href(phone: str | None) -> str:
    first = (phone or "").split("/")[0].split(";")[0]
    digits = "".join(ch for ch in first if ch.isdigit() or ch == "+")
    return f"tel:{digits}" if digits else ""


def truncate_title(title: str, max_len: int = 56) -> str:
    t = (title or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def reach_channels(
    email: str | None = None,
    phone: str | None = None,
    linkedin_url: str | None = None,
    website: str | None = None,
    source_url: str | None = None,
) -> list[dict]:
    """Ordered contact options: email → phone → LinkedIn → website → source page."""
    channels: list[dict] = []
    if email:
        channels.append({"label": "Email", "value": email, "href": f"mailto:{email}", "kind": "email"})
    if phone:
        channels.append({"label": "Phone", "value": phone, "href": tel_href(phone), "kind": "phone"})
    if linkedin_url:
        channels.append({"label": "LinkedIn", "value": "Open profile / page", "href": linkedin_url, "kind": "linkedin"})
    if website:
        short = website.replace("https://", "").replace("http://", "")
        channels.append({"label": "Website", "value": truncate_title(short, 42), "href": website, "kind": "web"})
    if source_url and source_url not in {website, linkedin_url}:
        short = source_url.replace("https://", "").replace("http://", "")
        label = "LinkedIn post" if "linkedin.com" in source_url.lower() else "Source page"
        channels.append({"label": label, "value": truncate_title(short, 42), "href": source_url, "kind": "source"})
    return channels
