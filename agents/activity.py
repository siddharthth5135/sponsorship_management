"""Live activity log for the continuous Lead Hunter agent."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.database import get_conn, init_db

_lock = threading.Lock()
_recent: deque[dict] = deque(maxlen=200)
_state: dict[str, Any] = {
    "enabled": True,
    "paused": False,
    "running_cycle": False,
    "phase": "booting",
    "current_step": "Starting Lead Hunter…",
    "cycle": 0,
    "started_at": None,
    "last_cycle_at": None,
    "next_cycle_at": None,
    "last_cycle_stats": {},
    "interval_minutes": 30,
    "finds_today": {
        "events": 0,
        "brands": 0,
        "candidates": 0,
        "tasks": 0,
        "matches": 0,
        "drafts": 0,
        "sent": 0,
        "followups": 0,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema() -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT DEFAULT 'info',
                agent_name TEXT NOT NULL,
                message TEXT NOT NULL,
                detail TEXT DEFAULT '',
                meta_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )


def set_state(**kwargs: Any) -> None:
    with _lock:
        _state.update(kwargs)


def get_state() -> dict:
    with _lock:
        return dict(_state)


def log(
    message: str,
    *,
    level: str = "info",
    agent: str = "Lead Hunter",
    detail: str = "",
    meta: dict | None = None,
    step: bool = False,
) -> dict:
    """Append a human-readable activity line (memory + SQLite)."""
    ensure_schema()
    entry = {
        "level": "step" if step else level,
        "agent_name": agent,
        "message": message[:500],
        "detail": (detail or "")[:800],
        "meta": meta or {},
        "created_at": _now(),
    }
    with _lock:
        if step:
            _state["current_step"] = message
            if meta and meta.get("phase"):
                _state["phase"] = meta["phase"]
        _recent.appendleft(entry)
        snapshot = dict(entry)

    try:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO agent_activity (level, agent_name, message, detail, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot["level"],
                    snapshot["agent_name"],
                    snapshot["message"],
                    snapshot["detail"],
                    json.dumps(snapshot["meta"]),
                ),
            )
            snapshot["id"] = cur.lastrowid
    except Exception:
        # Never crash the app on activity logging (esp. SQLite locked / OneDrive)
        snapshot["id"] = 0
    return snapshot


def bump_finds(**kwargs: int) -> None:
    with _lock:
        finds = dict(_state.get("finds_today") or {})
        for k, v in kwargs.items():
            finds[k] = int(finds.get(k) or 0) + int(v)
        _state["finds_today"] = finds


def recent(limit: int = 80) -> list[dict]:
    with _lock:
        mem = list(_recent)[:limit]
    if len(mem) >= min(limit, 20):
        out = []
        for e in mem:
            row = dict(e)
            row.setdefault("id", 0)
            out.append(row)
        return out
    ensure_schema()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_activity ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d.pop("meta_json") or "{}")
        except json.JSONDecodeError:
            d["meta"] = {}
        result.append(d)
    return result


def status_payload(limit: int = 60) -> dict:
    state = get_state()
    conversion = {}
    try:
        from agents.converter import conversion_snapshot

        conversion = conversion_snapshot()
    except Exception:
        conversion = {}
    return {
        "ok": True,
        "hunter": state,
        "activity": recent(limit),
        "conversion": conversion,
        "team": [
            {
                "id": "closer",
                "name": "Closer (main)",
                "does": "Converts clients: writes pitches and auto-sends emails from your Gmail without asking each time. Follows up if no reply. Logs every send on this page.",
            },
            {
                "id": "pitch_writer",
                "name": "Pitch Writer",
                "does": "Builds Blithchron + Gujarat sponsorship pitches (email + WhatsApp-ready copy) aimed at getting a call or yes.",
            },
            {
                "id": "fit_matcher",
                "name": "Fit Matcher",
                "does": "Keeps brand↔event fit scores fresh so pitches stay relevant.",
            },
            {
                "id": "event_scout",
                "name": "Event Scout (secondary)",
                "does": "Light top-up of new Gujarat events/brands every few cycles — feeds the conversion queue, not the main job.",
            },
        ],
    }
