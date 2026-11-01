"""
Continuous conversion agent — runs inside the web app while SponsorDesk is live.

Primary job: pitch + auto-message clients (no per-send approval).
Secondary: light scouting to refill the pipeline.
Open /agents to watch every send and step. Disable with LIVE_HUNTER=0.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone

from agents import activity
from agents.converter import conversion_config, run_conversion
from agents.discovery import load_config, run_discovery
from agents.orchestrator import agent_fit_matcher, log_run
from app.database import get_conn, init_db
from app.services.opportunity import rescore_all_events

_thread: threading.Thread | None = None
_stop = threading.Event()
_wake = threading.Event()
_started = False


def _iso_in(minutes: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _promote_brand_candidates(limit: int = 12) -> int:
    """Turn fresh brand web hits into prospect rows you can call."""
    added = 0
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM discoveries
            WHERE lead_type='brand' AND status='candidate'
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            d = dict(row)
            title = (d.get("title") or "").strip()[:180]
            if not title:
                continue
            url = (d.get("source_url") or "").strip()
            exists = conn.execute(
                "SELECT id FROM brands WHERE lower(name)=? OR (source_url!='' AND lower(source_url)=?)",
                (title.lower(), url.lower()),
            ).fetchone()
            if exists:
                conn.execute(
                    "UPDATE discoveries SET status='dismissed' WHERE id=?",
                    (d["id"],),
                )
                continue
            city = "Ahmedabad"
            blob = f"{title} {d.get('snippet') or ''} {d.get('query_used') or ''}".lower()
            for needle, city_name in (
                ("surat", "Surat"),
                ("vadodara", "Vadodara"),
                ("baroda", "Vadodara"),
                ("rajkot", "Rajkot"),
                ("gandhinagar", "Gandhinagar"),
            ):
                if needle in blob:
                    city = city_name
                    break
            category = "Local brand / D2C"
            if any(x in blob for x in ("edtech", "coding", "institute", "coaching")):
                category = "Edtech / coaching"
            elif any(x in blob for x in ("bank", "finance", "nbfc")):
                category = "Banking / finance"
            elif any(x in blob for x in ("fmcg", "beverage", "food")):
                category = "FMCG"
            cur = conn.execute(
                """
                INSERT INTO brands (
                    name, city, category, goal, status, notes, source_url,
                    discovery_reason, description, segment, conversion_tier, intent_signal
                ) VALUES (?, ?, ?, 'awareness', 'prospect', ?, ?, ?, ?, 'hunter', 'possible', 'latent')
                """,
                (
                    title,
                    city,
                    category,
                    "Auto-found by Lead Hunter — verify contact before outreach.",
                    url,
                    (d.get("why_chosen") or "")[:500],
                    (d.get("snippet") or "")[:400],
                ),
            )
            conn.execute(
                "UPDATE discoveries SET status='imported', imported_table='brands', imported_id=? WHERE id=?",
                (cur.lastrowid, d["id"]),
            )
            added += 1
            activity.log(
                f"New brand prospect: {title}",
                level="success",
                agent="Brand Scout",
                detail=url or (d.get("why_chosen") or ""),
                meta={"brand_id": cur.lastrowid, "city": city},
            )
    return added


def _light_scout() -> dict:
    """Secondary pass — refill inventory; not the main job."""
    activity.set_state(phase="scanning")
    activity.log(
        "Secondary scout — topping up events/brands for the conversion queue",
        agent="Event Scout",
        step=True,
        meta={"phase": "scanning"},
    )

    def on_progress(message: str, **meta) -> None:
        activity.log(
            message,
            level=meta.pop("level", "step"),
            agent=meta.pop("agent", "Event Scout"),
            detail=meta.pop("detail", ""),
            step=True,
            meta={"phase": meta.get("phase", "scanning"), **meta},
        )

    stats = run_discovery(progress=on_progress)
    events_added = int(stats.get("events_added") or 0)
    candidates = int(stats.get("candidates") or 0)
    activity.bump_finds(events=events_added, candidates=candidates)
    brands_added = _promote_brand_candidates()
    activity.bump_finds(brands=brands_added)
    with get_conn() as conn:
        tiers = rescore_all_events(conn)
    matches = agent_fit_matcher()
    activity.bump_finds(matches=matches)
    activity.log(
        f"Scout top-up: +{events_added} events, +{brands_added} brands, {candidates} candidates",
        level="success",
        agent="Event Scout",
        detail=f"Chase {tiers.get('chase', 0)} · matches refreshed {matches}",
    )
    return {
        "events_added": events_added,
        "brands_added": brands_added,
        "candidates": candidates,
        "matches": matches,
        "tiers": tiers,
    }


def _run_cycle() -> dict:
    activity.set_state(running_cycle=True, phase="converting")
    cfg = load_config()
    ccfg = conversion_config(cfg)
    cycle_n = int(activity.get_state().get("cycle") or 1)

    # 1) MAIN JOB — convert / pitch / auto-send
    conv = run_conversion(cfg)

    # 2) Keep fit scores warm every cycle (cheap, helps pitches)
    activity.log(
        "Refreshing brand ↔ event fit for next pitches…",
        agent="Fit Matcher",
        step=True,
        meta={"phase": "matching"},
    )
    matches = agent_fit_matcher()
    activity.bump_finds(matches=matches)

    # 3) SECONDARY — scout only every N cycles
    scout: dict = {}
    if cycle_n % int(ccfg["scout_every_n_cycles"]) == 0:
        scout = _light_scout()
    else:
        activity.log(
            f"Skipping heavy scout this cycle (runs every {ccfg['scout_every_n_cycles']} cycles)",
            agent="Event Scout",
            level="info",
        )

    sent = int((conv.get("send") or {}).get("sent") or 0) + int(
        (conv.get("followups") or {}).get("sent") or 0
    )
    snap = conv.get("snapshot") or {}
    summary = (
        f"Cycle #{cycle_n}: {sent} messages sent · "
        f"{snap.get('awaiting_reply', 0)} awaiting reply · "
        f"{snap.get('blithchron_unsent_email', 0)} Blithchron emails still queued"
    )
    log_run("Lead Hunter", "conversion_cycle", summary, sent, [])
    activity.log(summary, level="success", step=True, meta={"phase": "idle"})
    activity.set_state(phase="idle", current_step=summary)

    return {"conversion": conv, "matches": matches, "scout": scout, "sent": sent}


def _loop() -> None:
    activity.ensure_schema()
    cfg = load_config()
    interval_min = max(10, int(cfg.get("interval_minutes", 30)))
    activity.set_state(
        enabled=True,
        paused=False,
        started_at=datetime.now(timezone.utc).isoformat(),
        interval_minutes=interval_min,
        phase="idle",
        current_step="Warming up — first conversion pass in ~20 seconds",
    )
    activity.log(
        "Closer is online — will pitch and auto-send while this app is running",
        level="success",
        detail=(
            f"Conversion every {interval_min} min. "
            "Emails send without asking you. Watch every message on /agents. "
            "Needs Gmail App Password on Outreach."
        ),
    )

    # Short delay so uvicorn finishes boot before first network scan
    if _stop.wait(20):
        return

    while not _stop.is_set():
        state = activity.get_state()
        if state.get("paused"):
            activity.set_state(
                phase="paused",
                current_step="Paused — tap Resume on the Agents page",
                running_cycle=False,
            )
            _wake.wait(5)
            _wake.clear()
            continue

        cycle = int(state.get("cycle") or 0) + 1
        activity.set_state(cycle=cycle)
        try:
            stats = _run_cycle()
            activity.set_state(
                last_cycle_at=datetime.now(timezone.utc).isoformat(),
                last_cycle_stats=stats,
                running_cycle=False,
                phase="idle",
                current_step=f"Sleeping until next cycle ({interval_min} min)",
                next_cycle_at=_iso_in(interval_min),
            )
        except Exception as exc:
            activity.set_state(running_cycle=False, phase="error")
            activity.log(
                f"Cycle failed: {exc}",
                level="error",
                detail="Will retry on the next interval",
                step=True,
                meta={"phase": "error"},
            )
            activity.set_state(
                current_step="Error — retrying after interval",
                next_cycle_at=_iso_in(interval_min),
            )

        # Sleep in chunks so pause / run-now can wake us
        deadline = time.monotonic() + interval_min * 60
        while time.monotonic() < deadline and not _stop.is_set():
            if activity.get_state().get("paused"):
                break
            if _wake.wait(timeout=2):
                _wake.clear()
                if not activity.get_state().get("paused"):
                    break  # run now


def start_live_hunter() -> bool:
    """Start background thread once. Returns False if disabled or already running."""
    global _thread, _started
    if os.environ.get("LIVE_HUNTER", "1").strip() in ("0", "false", "off", "no"):
        activity.set_state(
            enabled=False,
            phase="disabled",
            current_step="Disabled via LIVE_HUNTER=0",
        )
        return False
    if _started and _thread and _thread.is_alive():
        return False
    init_db()
    activity.ensure_schema()
    _stop.clear()
    _wake.clear()
    _thread = threading.Thread(target=_loop, name="lead-hunter", daemon=True)
    _thread.start()
    _started = True
    return True


def stop_live_hunter() -> None:
    _stop.set()
    _wake.set()


def request_run_now() -> None:
    activity.set_state(paused=False)
    _wake.set()
    activity.log("Manual run requested — waking hunter now", level="info", step=True)


def set_paused(paused: bool) -> None:
    activity.set_state(paused=paused)
    _wake.set()
    if paused:
        activity.log("Hunter paused by you", level="warn", step=True, meta={"phase": "paused"})
    else:
        activity.log("Hunter resumed", level="success", step=True, meta={"phase": "idle"})


def is_alive() -> bool:
    return bool(_thread and _thread.is_alive())
