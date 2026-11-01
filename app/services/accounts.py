"""Multi-Gmail account pool — rotate sends + monitor every inbox."""

from __future__ import annotations

import itertools
import json
import threading
from typing import Any

from app.paths import sender_profile_path
from app.services.emails import sender_profile

_lock = threading.Lock()
_rr = itertools.count(0)


def _default_accounts(profile: dict) -> list[dict]:
    """Build account list from profile (supports legacy single-account fields)."""
    accounts = profile.get("gmail_accounts")
    if isinstance(accounts, list) and accounts:
        out = []
        for a in accounts:
            email = (a.get("email") or "").strip().lower()
            if not email:
                continue
            out.append(
                {
                    "email": email,
                    "gmail_app_password": (a.get("gmail_app_password") or "").strip(),
                    "label": a.get("label") or email,
                    "enabled": a.get("enabled", True),
                }
            )
        if out:
            return out
    # Legacy single inbox
    email = (profile.get("email") or "").strip().lower()
    if email:
        return [
            {
                "email": email,
                "gmail_app_password": (profile.get("gmail_app_password") or "").strip(),
                "label": "Primary",
                "enabled": True,
            }
        ]
    return []


def ensure_dual_defaults(profile: dict | None = None) -> dict:
    """Make sure both Siddharth inboxes exist in the profile structure."""
    profile = dict(profile or sender_profile())
    wanted = [
        {
            "email": "siddharththpatel@gmail.com",
            "label": "Primary",
            "gmail_app_password": "",
            "enabled": True,
        },
        {
            "email": "siddharthth5135@gmail.com",
            "label": "Secondary",
            "gmail_app_password": "",
            "enabled": True,
        },
    ]
    existing = {a["email"]: a for a in _default_accounts(profile)}
    # Preserve passwords already saved
    if profile.get("email") and (profile.get("gmail_app_password") or "").strip():
        primary = (profile.get("email") or "").strip().lower()
        if primary in existing:
            existing[primary]["gmail_app_password"] = (
                existing[primary].get("gmail_app_password")
                or profile.get("gmail_app_password")
                or ""
            ).strip()
        else:
            existing[primary] = {
                "email": primary,
                "label": "Primary",
                "gmail_app_password": (profile.get("gmail_app_password") or "").strip(),
                "enabled": True,
            }
    merged = []
    for w in wanted:
        cur = existing.get(w["email"], w)
        merged.append(
            {
                "email": w["email"],
                "label": cur.get("label") or w["label"],
                "gmail_app_password": (cur.get("gmail_app_password") or "").strip(),
                "enabled": cur.get("enabled", True),
            }
        )
    # Keep any extra accounts user added
    for email, a in existing.items():
        if email not in {m["email"] for m in merged}:
            merged.append(a)
    profile["gmail_accounts"] = merged
    # Keep legacy fields pointing at first ready account (or first)
    ready = next((a for a in merged if (a.get("gmail_app_password") or "").strip()), None)
    primary = ready or merged[0]
    profile["email"] = primary["email"]
    if ready:
        profile["gmail_app_password"] = ready["gmail_app_password"]
    return profile


def save_profile(profile: dict) -> dict:
    profile = ensure_dual_defaults(profile)
    path = sender_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return profile


def list_accounts() -> list[dict]:
    return ensure_dual_defaults(sender_profile()).get("gmail_accounts") or []


def ready_accounts() -> list[dict]:
    return [
        a
        for a in list_accounts()
        if a.get("enabled", True) and (a.get("email") or "").strip() and (a.get("gmail_app_password") or "").strip()
    ]


def any_gmail_ready() -> bool:
    return bool(ready_accounts())


def pick_sender() -> dict[str, Any]:
    """Round-robin across ready Gmail accounts."""
    ready = ready_accounts()
    if not ready:
        raise ValueError("No Gmail App Password configured on any account")
    with _lock:
        idx = next(_rr) % len(ready)
        acct = ready[idx]
    profile = sender_profile()
    return {
        "name": profile.get("name") or "Siddharth Patel",
        "title": profile.get("title") or "",
        "phone": profile.get("phone") or "",
        "email": acct["email"],
        "gmail_app_password": acct["gmail_app_password"],
        "label": acct.get("label") or acct["email"],
    }


def account_status() -> list[dict]:
    out = []
    for a in list_accounts():
        out.append(
            {
                "email": a["email"],
                "label": a.get("label") or a["email"],
                "ready": bool((a.get("gmail_app_password") or "").strip()),
                "enabled": a.get("enabled", True),
            }
        )
    return out
