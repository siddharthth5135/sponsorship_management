import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from agents.discovery import migrate as migrate_discovery
from agents.orchestrator import agent_fit_matcher

from app import ui
from app.database import get_conn, init_db
from app.services.commission import calc_commission
from app.paths import sender_profile_path
from app.services.emails import gmail_compose_url, sender_profile
from app.services.bounces import check_bounces
from app.services.mailer import MailerError, gmail_ready, send_email, send_many
from app.services.matching import CATEGORIES
from app.services.messaging import enrich_channels
from app.services.opportunity import rescore_all_events, score_opportunity

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["stage_label"] = ui.stage_label
templates.env.filters["why_summary"] = ui.why_summary
templates.env.filters["truncate_title"] = ui.truncate_title
templates.env.globals["ui"] = ui
templates.env.globals["CATEGORIES"] = CATEGORIES


def _save_sender_profile(updates: dict) -> dict:
    profile = sender_profile()
    profile.update({k: v for k, v in updates.items() if v is not None})
    path = sender_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return profile


def _outreach_redirect(msg: str = "", error: str = "", page: str = "/outreach/events") -> RedirectResponse:
    qs = []
    if msg:
        qs.append(f"ok={quote(msg)}")
    if error:
        qs.append(f"err={quote(error)}")
    return RedirectResponse(page + (("?" + "&".join(qs)) if qs else ""), status_code=303)


def _safe_return_page(return_to: str, default: str) -> str:
    allowed = (
        "/outreach/events",
        "/outreach/brands",
        "/blithchron",
        "/events",
        "/brands",
    )
    if return_to in allowed or return_to.startswith("/outreach/"):
        return return_to
    return default


def _outreach_page_for(target_type: str | None) -> str:
    return "/outreach/brands" if target_type == "brand" else "/outreach/events"

app = FastAPI(title="SponsorDesk", version="2.0.0")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

ACCESS_COOKIE = "sponsordesk_access"
PUBLIC_PATHS = {"/api/health", "/login", "/static"}


class AccessGateMiddleware(BaseHTTPMiddleware):
    """Optional site password via env ACCESS_PASSWORD — recommended on Render."""

    async def dispatch(self, request: Request, call_next):
        password = (os.environ.get("ACCESS_PASSWORD") or "").strip()
        if not password:
            return await call_next(request)
        path = request.url.path
        if path.startswith("/static") or path in ("/api/health", "/login"):
            return await call_next(request)
        token = request.cookies.get(ACCESS_COOKIE)
        expected = secrets.compare_digest(token or "", _access_token(password))
        if expected:
            return await call_next(request)
        if path.startswith("/api/"):
            return Response("Unauthorized", status_code=401)
        return RedirectResponse("/login?next=" + quote(path), status_code=303)


def _access_token(password: str) -> str:
    import hashlib

    return hashlib.sha256(f"sponsordesk:{password}".encode()).hexdigest()


app.add_middleware(AccessGateMiddleware)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/", err: str = ""):
    if not (os.environ.get("ACCESS_PASSWORD") or "").strip():
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(
        f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SponsorDesk login</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f8fafc;margin:0;padding:2rem 1rem;}}
.card{{max-width:380px;margin:10vh auto;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:1.5rem;}}
h1{{font-size:1.25rem;margin:0 0 .5rem}} p{{color:#64748b;font-size:14px}}
input,button{{width:100%;padding:.75rem;margin-top:.5rem;font:inherit;border-radius:10px;border:1px solid #cbd5e1;box-sizing:border-box}}
button{{background:#2563eb;color:#fff;border:none;font-weight:600;margin-top:1rem}}
.err{{color:#b91c1c;font-size:13px}}
</style></head><body><div class="card">
<h1>SponsorDesk</h1>
<p>Enter the access password to use the CRM on phone or web.</p>
{"<p class=err>Wrong password</p>" if err else ""}
<form method="post" action="/login">
<input type="hidden" name="next" value="{next or "/"}">
<input name="password" type="password" placeholder="Access password" autofocus required>
<button type="submit">Open app</button>
</form></div></body></html>"""
    )


@app.post("/login")
def login_submit(password: str = Form(""), next: str = Form("/")):
    expected = (os.environ.get("ACCESS_PASSWORD") or "").strip()
    if not expected or not secrets.compare_digest(password, expected):
        return RedirectResponse("/login?err=1&next=" + quote(next or "/"), status_code=303)
    resp = RedirectResponse(next if next.startswith("/") else "/", status_code=303)
    resp.set_cookie(
        ACCESS_COOKIE,
        _access_token(expected),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return resp


@app.on_event("startup")
def startup() -> None:
    init_db()
    migrate_discovery()
    _seed_blithchron_if_empty()
    try:
        from agents.activity import ensure_schema
        from agents.live_hunter import start_live_hunter

        ensure_schema()
        start_live_hunter()
    except Exception:
        pass


def _seed_blithchron_if_empty() -> None:
    try:
        with get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM brands WHERE segment IN ('blithchron27','blithchron27_local')"
            ).fetchone()[0]
        if n > 0:
            return
        import sys

        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from scripts.build_blithchron_pack import load_db

        load_db()
    except Exception:
        # Don't block boot if seed fails (missing openpyxl etc.) — Excel build is optional
        try:
            import sys

            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from scripts.blithchron_leads_master import LEADS
            from scripts.blithchron_local_leads import LOCAL_LEADS
            from scripts.build_blithchron_pack import _upsert_brand
            from app.services.emails import sender_profile as sp

            sender = sp()
            with get_conn() as conn:
                ev = conn.execute(
                    "SELECT id FROM events WHERE name LIKE 'Blithchron%' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not ev:
                    cur = conn.execute(
                        """
                        INSERT INTO events (name, city, category, event_date, date_label, planning_stage,
                            footfall_estimate, organizer_email, opportunity_tier, opportunity_score, discovery_reason)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            "Blithchron '27 — IIT Gandhinagar Cultural Fest",
                            "Gandhinagar",
                            "College cultural fest",
                            "2027-02-04",
                            "4–7 Feb 2027",
                            "seeking_sponsors",
                            22000,
                            "blithchron@iitgn.ac.in",
                            "chase",
                            95,
                            "blithchron_pack",
                        ),
                    )
                    event_id = cur.lastrowid
                else:
                    event_id = ev["id"]
                for L in LEADS:
                    _upsert_brand(conn, L, "blithchron27", event_id, sender, "blithchron27")
                for L in LOCAL_LEADS:
                    _upsert_brand(conn, L, "blithchron27_local", event_id, sender, "blithchron27_local")
        except Exception:
            pass


def fetch_all(table: str, order: str = "id DESC") -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
        return [dict(r) for r in rows]


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with get_conn() as conn:
        stats = {
            "events": conn.execute(
                "SELECT COUNT(*) FROM events WHERE ifnull(opportunity_tier,'chase') IN ('chase','research')"
            ).fetchone()[0],
            "events_chase": conn.execute(
                "SELECT COUNT(*) FROM events WHERE opportunity_tier='chase'"
            ).fetchone()[0],
            "brands": conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0],
            "matches_pending": conn.execute(
                "SELECT COUNT(*) FROM matches WHERE status='suggested'"
            ).fetchone()[0],
            "outreach_drafts": conn.execute(
                "SELECT COUNT(*) FROM outreach WHERE status='draft'"
            ).fetchone()[0],
            "deals_open": conn.execute(
                "SELECT COUNT(*) FROM deals WHERE status NOT IN ('closed','lost')"
            ).fetchone()[0],
            "founder_tasks": conn.execute(
                "SELECT COUNT(*) FROM founder_tasks WHERE status='pending'"
            ).fetchone()[0],
        }
        tasks = conn.execute(
            "SELECT * FROM founder_tasks WHERE status='pending' ORDER BY id LIMIT 10"
        ).fetchall()
        recent_runs = conn.execute(
            "SELECT * FROM agent_runs ORDER BY id DESC LIMIT 8"
        ).fetchall()
        discoveries = conn.execute(
            "SELECT * FROM discoveries WHERE status='candidate' ORDER BY id DESC LIMIT 40"
        ).fetchall()
        top_matches = conn.execute(
            """
            SELECT m.*, e.name AS event_name, b.name AS brand_name
            FROM matches m
            JOIN events e ON e.id = m.event_id
            JOIN brands b ON b.id = m.brand_id
            ORDER BY m.fit_score DESC LIMIT 6
            """
        ).fetchall()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "tasks": [dict(t) for t in tasks],
            "recent_runs": [dict(r) for r in recent_runs],
            "discoveries": [dict(d) for d in discoveries],
            "top_matches": [dict(m) for m in top_matches],
        },
    )


@app.get("/events", response_class=HTMLResponse)
def events_page(request: Request):
    show = (request.query_params.get("show") or "actionable").lower()
    with get_conn() as conn:
        if show == "all":
            rows = conn.execute(
                """
                SELECT * FROM events
                ORDER BY CASE opportunity_tier
                  WHEN 'chase' THEN 0 WHEN 'research' THEN 1 ELSE 2 END,
                  opportunity_score DESC, id DESC
                """
            ).fetchall()
        elif show == "skip":
            rows = conn.execute(
                "SELECT * FROM events WHERE opportunity_tier='skip' ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE ifnull(opportunity_tier,'research') IN ('chase','research')
                ORDER BY CASE opportunity_tier WHEN 'chase' THEN 0 ELSE 1 END,
                  opportunity_score DESC, id DESC
                """
            ).fetchall()
        counts = {
            "chase": conn.execute(
                "SELECT COUNT(*) FROM events WHERE opportunity_tier='chase'"
            ).fetchone()[0],
            "research": conn.execute(
                "SELECT COUNT(*) FROM events WHERE opportunity_tier='research'"
            ).fetchone()[0],
            "skip": conn.execute(
                "SELECT COUNT(*) FROM events WHERE opportunity_tier='skip'"
            ).fetchone()[0],
        }
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "events": [dict(r) for r in rows],
            "show": show,
            "counts": counts,
        },
    )


@app.post("/events")
def create_event(
    name: str = Form(...),
    city: str = Form(...),
    category: str = Form(...),
    event_date: str = Form(""),
    planning_stage: str = Form("planning"),
    footfall_estimate: int = Form(0),
    organizer_name: str = Form(""),
    organizer_phone: str = Form(""),
    organizer_email: str = Form(""),
    notes: str = Form(""),
    description: str = Form(""),
    date_label: str = Form(""),
    audience: str = Form(""),
    contact_role: str = Form(""),
    website: str = Form(""),
    linkedin_url: str = Form(""),
    source_url: str = Form(""),
    discovery_id: int = Form(0),
):
    draft = {
        "name": name,
        "city": city,
        "category": category,
        "event_date": event_date,
        "planning_stage": planning_stage,
        "footfall_estimate": footfall_estimate,
        "organizer_name": organizer_name,
        "organizer_phone": organizer_phone,
        "organizer_email": organizer_email,
        "notes": notes,
        "description": description,
        "discovery_reason": "Promoted from web discovery after your review." if discovery_id else "",
        "source_url": source_url,
        "website": website,
        "linkedin_url": linkedin_url,
        "contact_role": contact_role,
        "audience": audience,
    }
    opp_score, opp_tier, opp_reason = score_opportunity(draft)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO events (name, city, category, event_date, planning_stage,
                footfall_estimate, organizer_name, organizer_phone, organizer_email, notes,
                description, date_label, audience, contact_role, website, linkedin_url, source_url, discovery_reason,
                opportunity_score, opportunity_tier, opportunity_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                city,
                category,
                event_date,
                planning_stage,
                footfall_estimate,
                organizer_name,
                organizer_phone,
                organizer_email,
                notes,
                description,
                date_label,
                audience,
                contact_role,
                website,
                linkedin_url,
                source_url,
                draft["discovery_reason"],
                opp_score,
                opp_tier,
                opp_reason,
            ),
        )
        if discovery_id:
            conn.execute(
                "UPDATE discoveries SET status='imported', imported_table='events', imported_id=? WHERE id=?",
                (cur.lastrowid, discovery_id),
            )
    return RedirectResponse("/events", status_code=303)


@app.post("/events/{event_id}/loi")
def mark_loi_signed(event_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE events SET loi_signed=1, updated_at=datetime('now') WHERE id=?",
            (event_id,),
        )
    return RedirectResponse("/events", status_code=303)


@app.post("/events/{event_id}/delete")
def delete_event(event_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM matches WHERE event_id=?", (event_id,))
        conn.execute("DELETE FROM deals WHERE event_id=?", (event_id,))
        conn.execute("DELETE FROM outreach WHERE target_type='event' AND target_id=? AND status='draft'", (event_id,))
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    return RedirectResponse("/events", status_code=303)


@app.get("/brands", response_class=HTMLResponse)
def brands_page(request: Request):
    return templates.TemplateResponse(
        "brands.html", {"request": request, "brands": fetch_all("brands")}
    )


@app.post("/brands")
def create_brand(
    name: str = Form(...),
    city: str = Form(...),
    category: str = Form(...),
    budget_min: int = Form(0),
    budget_max: int = Form(0),
    goal: str = Form("awareness"),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    status: str = Form("prospect"),
    notes: str = Form(""),
    description: str = Form(""),
    target_categories: list[str] = Form([]),
    contact_role: str = Form(""),
    website: str = Form(""),
    linkedin_url: str = Form(""),
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO brands (name, city, category, budget_min, budget_max, goal,
                contact_name, contact_email, contact_phone, status, notes,
                description, target_categories, contact_role, website, linkedin_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                city,
                category,
                budget_min,
                budget_max,
                goal,
                contact_name,
                contact_email,
                contact_phone,
                status,
                notes,
                description,
                ", ".join(target_categories),
                contact_role,
                website,
                linkedin_url,
            ),
        )
    return RedirectResponse("/brands", status_code=303)


@app.post("/brands/{brand_id}/delete")
def delete_brand(brand_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM matches WHERE brand_id=?", (brand_id,))
        conn.execute("DELETE FROM outreach WHERE target_type='brand' AND target_id=? AND status='draft'", (brand_id,))
        conn.execute("DELETE FROM brands WHERE id=?", (brand_id,))
    return RedirectResponse("/brands", status_code=303)


def grouped_matches() -> list[dict]:
    """One entry per brand, with every event it fits (best first)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id AS match_id, m.fit_score, m.fit_tier, m.match_reason, m.status,
                   m.organizer_approved, m.brand_id,
                   e.id AS event_id, e.name AS event_name, e.city AS event_city,
                   e.date_label, e.event_date, e.category AS event_category, e.loi_signed
            FROM matches m
            JOIN events e ON e.id = m.event_id
            ORDER BY m.fit_score DESC
            """
        ).fetchall()
        brands = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM brands").fetchall()}
    groups: dict[int, dict] = {}
    for r in rows:
        r = dict(r)
        g = groups.setdefault(r["brand_id"], {"brand": brands[r["brand_id"]], "events": []})
        g["events"].append(r)
    result = list(groups.values())
    for g in result:
        g["best"] = g["events"][0]["fit_score"]
    result.sort(key=lambda g: (-len(g["events"]), -g["best"]))
    return result


@app.get("/matches", response_class=HTMLResponse)
def matches_page(request: Request):
    groups = grouped_matches()
    total = sum(len(g["events"]) for g in groups)
    return templates.TemplateResponse(
        "matches.html", {"request": request, "groups": groups, "total": total}
    )


@app.post("/matches/run")
def run_matching():
    count = agent_fit_matcher()
    return RedirectResponse(f"/matches?scored={count}", status_code=303)


@app.post("/matches/{match_id}/approve")
def approve_match(match_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE matches SET organizer_approved=1, status='approved' WHERE id=?",
            (match_id,),
        )
    return RedirectResponse("/matches", status_code=303)


def _load_outreach_items(sender: dict, target_type: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT o.*,
                   CASE o.target_type WHEN 'event' THEN e.name ELSE b.name END AS target_name,
                   CASE o.target_type WHEN 'event' THEN e.contact_role ELSE b.contact_role END AS target_contact_role,
                   CASE o.target_type WHEN 'event' THEN e.organizer_phone ELSE b.contact_phone END AS target_phone,
                   CASE o.target_type WHEN 'event' THEN e.website ELSE b.website END AS target_website,
                   CASE o.target_type WHEN 'event' THEN e.linkedin_url ELSE b.linkedin_url END AS target_linkedin,
                   CASE o.target_type WHEN 'event' THEN e.source_url ELSE b.source_url END AS target_source
            FROM outreach o
            LEFT JOIN events e ON o.target_type='event' AND e.id=o.target_id
            LEFT JOIN brands b ON o.target_type='brand' AND b.id=o.target_id
            WHERE o.target_type=?
            ORDER BY CASE
              WHEN o.status='bounced' THEN 0
              WHEN o.status='sent' THEN 2
              ELSE 1 END, o.id
            """,
            (target_type,),
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        from_email = item.get("from_email") or sender["email"]
        item["from_email"] = from_email
        item["is_sent"] = item.get("status") == "sent"
        item["is_bounced"] = item.get("status") == "bounced"
        item["gmail_url"] = (
            gmail_compose_url(item["to_email"], item["subject"], item["body"], from_email)
            if item.get("to_email")
            else ""
        )
        item["reach"] = ui.reach_channels(
            item.get("to_email"),
            item.get("target_phone"),
            item.get("target_linkedin"),
            item.get("target_website"),
            item.get("target_source"),
        )
        items.append(item)
    return items


@app.get("/outreach")
def outreach_index():
    return RedirectResponse("/outreach/events", status_code=303)


@app.get("/outreach/events", response_class=HTMLResponse)
def outreach_events_page(request: Request):
    return _render_outreach_page(request, "event")


@app.get("/outreach/brands", response_class=HTMLResponse)
def outreach_brands_page(request: Request):
    return _render_outreach_page(request, "brand")


def _render_outreach_page(request: Request, target_type: str):
    sender = sender_profile()
    items = _load_outreach_items(sender, target_type)
    pending = [i for i in items if not i["is_sent"]]
    sent = [i for i in items if i["is_sent"]]
    meta = {
        "event": {
            "title": "Event outreach",
            "hint": "Win organizers first — get their deck and permission to sell open slots.",
            "page": "/outreach/events",
            "other_label": "Brand outreach",
            "other_href": "/outreach/brands",
        },
        "brand": {
            "title": "Brand outreach",
            "hint": "Pitch your brokerage (negotiable rates + a meeting this week) — not specific event seats. Prioritize High-conversion education / IT brands on the Brands page.",
            "page": "/outreach/brands",
            "other_label": "Event outreach",
            "other_href": "/outreach/events",
        },
    }[target_type]
    sendable = [i for i in pending if (i.get("to_email") or "").strip()]
    return templates.TemplateResponse(
        "outreach.html",
        {
            "request": request,
            "sender": sender,
            "pending": pending,
            "sent": sent,
            "remaining": len(pending),
            "sent_count": len(sent),
            "sendable_count": len(sendable),
            "total": len(items),
            "meta": meta,
            "target_type": target_type,
            "gmail_ready": gmail_ready(),
            "flash_ok": request.query_params.get("ok", ""),
            "flash_err": request.query_params.get("err", ""),
        },
    )


@app.post("/outreach/settings")
def save_outreach_settings(
    gmail_app_password: str = Form(""),
    return_to: str = Form("/outreach/events"),
):
    page = _safe_return_page(return_to, "/outreach/events")
    _save_sender_profile({"gmail_app_password": gmail_app_password.strip()})
    if gmail_app_password.strip():
        return _outreach_redirect("Gmail App Password saved. You can use Send automatically now.", page=page)
    return _outreach_redirect(error="App Password was cleared. Auto-send is off until you add one again.", page=page)


@app.post("/outreach/check-bounces")
def check_outreach_bounces(return_to: str = Form("/outreach/brands")):
    page = _safe_return_page(return_to, "/outreach/brands")
    try:
        result = check_bounces()
    except MailerError as exc:
        return _outreach_redirect(error=str(exc), page=page)
    n = result["outreach_updated"]
    if n:
        addrs = ", ".join(result["addresses"][:5])
        extra = f" (+{len(result['addresses']) - 5} more)" if len(result["addresses"]) > 5 else ""
        return _outreach_redirect(
            f"Marked {n} as bounced from Gmail failure mail. Fix the address and resend: {addrs}{extra}",
            page=page,
        )
    if result["bounces_seen"]:
        return _outreach_redirect(
            f"Found {result['bounces_seen']} bounce notice(s) in Gmail, but none matched a sent outreach draft.",
            page=page,
        )
    return _outreach_redirect("No bounce / delivery-failure emails found in recent Gmail inbox.", page=page)


@app.post("/outreach/send-all")
def send_all_outreach(target_type: str = Form(...)):
    if target_type not in ("event", "brand"):
        return _outreach_redirect(error="Invalid outreach type.")
    page = _outreach_page_for(target_type)
    with get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM outreach
                WHERE target_type=? AND status!='sent'
                  AND ifnull(to_email,'') != ''
                ORDER BY id
                """,
                (target_type,),
            ).fetchall()
        ]
        if not rows:
            return _outreach_redirect(
                error="Nothing to send — no drafts with an email address left on this page.",
                page=page,
            )
        try:
            sent_n, errors = send_many(rows)
        except MailerError as exc:
            return _outreach_redirect(error=str(exc), page=page)
        for item in rows:
            if item.get("_ok"):
                conn.execute(
                    """
                    UPDATE outreach
                    SET status='sent', founder_approved=1, sent_at=datetime('now'), send_error=''
                    WHERE id=?
                    """,
                    (item["id"],),
                )
            else:
                err = next((e for e in errors if str(item.get("to_email", "")) in e), "Send failed")
                conn.execute(
                    "UPDATE outreach SET send_error=? WHERE id=?",
                    (err[:400], item["id"]),
                )
    skipped = len(rows) - sent_n
    if sent_n and not skipped:
        return _outreach_redirect(f"Sent all {sent_n} emails automatically.", page=page)
    if sent_n:
        return _outreach_redirect(
            f"Sent {sent_n}. {skipped} failed — check send errors on the remaining drafts.",
            page=page,
        )
    return _outreach_redirect(error="Could not send any emails. " + ("; ".join(errors[:2]) if errors else ""), page=page)


@app.post("/outreach/{outreach_id}/send")
def send_outreach_now(outreach_id: int, return_to: str = Form("")):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM outreach WHERE id=?", (outreach_id,)).fetchone()
        if not row:
            return _outreach_redirect(error="Draft not found.")
        item = dict(row)
        page = _safe_return_page(return_to, _outreach_page_for(item.get("target_type"))) if return_to else _outreach_page_for(item.get("target_type"))
        if item.get("status") == "sent":
            return _outreach_redirect(error="This email was already sent.", page=page)
        try:
            send_email(
                item.get("to_email") or "",
                item.get("subject") or "",
                item.get("body") or "",
                item.get("to_name") or "",
            )
            conn.execute(
                """
                UPDATE outreach
                SET status='sent', founder_approved=1, sent_at=datetime('now'), send_error=''
                WHERE id=?
                """,
                (outreach_id,),
            )
        except MailerError as exc:
            conn.execute("UPDATE outreach SET send_error=? WHERE id=?", (str(exc), outreach_id))
            return _outreach_redirect(error=str(exc), page=page)
    verb = "Resent" if item.get("status") == "bounced" else "Sent"
    return _outreach_redirect(f"{verb} to {item.get('to_email')}.", page=page)


@app.post("/outreach/{outreach_id}/sent")
def mark_outreach_sent(outreach_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT target_type FROM outreach WHERE id=?", (outreach_id,)).fetchone()
        page = _outreach_page_for(row["target_type"] if row else None)
        conn.execute(
            "UPDATE outreach SET status='sent', founder_approved=1, sent_at=datetime('now') WHERE id=?",
            (outreach_id,),
        )
    return _outreach_redirect("Marked as sent.", page=page)


@app.post("/outreach/{outreach_id}/fix-email")
def fix_outreach_email(outreach_id: int, to_email: str = Form(...)):
    cleaned = (to_email or "").strip().lower()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM outreach WHERE id=?", (outreach_id,)).fetchone()
        if not row:
            return _outreach_redirect(error="Draft not found.")
        item = dict(row)
        page = _outreach_page_for(item.get("target_type"))
        if not cleaned or "@" not in cleaned:
            return _outreach_redirect(error="Enter a valid email address.", page=page)
        conn.execute(
            """
            UPDATE outreach
            SET to_email=?, status='approved', send_error='', founder_approved=1
            WHERE id=?
            """,
            (cleaned, outreach_id),
        )
        # Keep brand/event contact in sync when this was a brand bounce
        if item.get("target_type") == "brand" and item.get("target_id"):
            conn.execute(
                "UPDATE brands SET contact_email=? WHERE id=?",
                (cleaned, item["target_id"]),
            )
        elif item.get("target_type") == "event" and item.get("target_id"):
            conn.execute(
                "UPDATE events SET organizer_email=? WHERE id=?",
                (cleaned, item["target_id"]),
            )
    return _outreach_redirect(f"Address updated to {cleaned}. You can resend now.", page=page)


@app.post("/discoveries/{discovery_id}/dismiss")
def dismiss_discovery(discovery_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE discoveries SET status='dismissed' WHERE id=?", (discovery_id,))
    return RedirectResponse("/", status_code=303)


@app.post("/discoveries/{discovery_id}/promote-event")
def promote_discovery_event(discovery_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM discoveries WHERE id=?", (discovery_id,)).fetchone()
        if not row:
            return RedirectResponse("/?err=Discovery+not+found", status_code=303)
        d = dict(row)
        title = (d.get("title") or "Untitled event").strip()[:200]
        city = "Ahmedabad"
        blob = f"{title} {d.get('snippet') or ''} {d.get('query_used') or ''}".lower()
        for needle, label in (
            ("surat", "Surat"),
            ("vadodara", "Vadodara"),
            ("rajkot", "Rajkot"),
            ("gandhinagar", "Gandhinagar"),
            ("bhavnagar", "Bhavnagar"),
            ("anand", "Anand"),
            ("ahmedabad", "Ahmedabad"),
        ):
            if needle in blob:
                city = label
                break
        category = "Talk / community event"
        if any(x in blob for x in ("marathon", "run ")):
            category = "Marathon / sports"
        elif any(x in blob for x in ("tech", "hackathon")):
            category = "College tech fest"
        elif any(x in blob for x in ("cultural", "garba", "fest")):
            category = "College cultural fest"
        elif any(x in blob for x in ("startup", "conference", "summit", "expo")):
            category = "Startup / business conference"
        cur = conn.execute(
            """
            INSERT INTO events (
                name, city, category, planning_stage, notes, description,
                website, source_url, discovery_reason, date_label
            ) VALUES (?, ?, ?, 'seeking_sponsors', ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                city,
                category,
                "Promoted from web discovery — verify contact before outreach.",
                (d.get("snippet") or "")[:400],
                d.get("source_url") or "",
                d.get("source_url") or "",
                d.get("why_chosen") or "Promoted from discovery queue.",
                "Verify on source page",
            ),
        )
        conn.execute(
            "UPDATE discoveries SET status='imported', imported_table='events', imported_id=? WHERE id=?",
            (cur.lastrowid, discovery_id),
        )
    return RedirectResponse("/events", status_code=303)


@app.post("/agents/run-event-scout")
def run_event_scout_now():
    from agents.orchestrator import agent_event_scout

    n = agent_event_scout(include_discovery=True)
    return RedirectResponse(
        f"/events?ok={quote(f'Event Scout finished ({n}). Only chase/research events are shown.')}",
        status_code=303,
    )


@app.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request, ok: str = ""):
    from agents.activity import status_payload

    payload = status_payload(80)
    with get_conn() as conn:
        recent_runs = conn.execute(
            "SELECT * FROM agent_runs ORDER BY id DESC LIMIT 20"
        ).fetchall()
    hunter = payload["hunter"]
    return templates.TemplateResponse(
        "agents.html",
        {
            "request": request,
            "ok": ok,
            "hunter": hunter,
            "finds": hunter.get("finds_today") or {},
            "conversion": payload.get("conversion") or {},
            "activity": payload["activity"],
            "team": payload["team"],
            "recent_runs": [dict(r) for r in recent_runs],
        },
    )


@app.post("/agents/run-now")
def agents_run_now():
    from agents.live_hunter import request_run_now

    request_run_now()
    return RedirectResponse(
        "/agents?ok=" + quote("Closer waking — pitching and auto-sending now."),
        status_code=303,
    )


@app.post("/agents/pause")
def agents_pause():
    from agents.live_hunter import set_paused

    set_paused(True)
    return RedirectResponse("/agents?ok=" + quote("Hunter paused."), status_code=303)


@app.post("/agents/resume")
def agents_resume():
    from agents.live_hunter import set_paused

    set_paused(False)
    return RedirectResponse("/agents?ok=" + quote("Hunter resumed."), status_code=303)


@app.get("/api/agents/live")
def api_agents_live():
    from agents.activity import status_payload
    from agents.live_hunter import is_alive

    payload = status_payload(80)
    payload["hunter"]["thread_alive"] = is_alive()
    return payload


@app.post("/events/rescore")
def rescore_events():
    with get_conn() as conn:
        counts = rescore_all_events(conn)
        # Drop skip-tier noise from outreach drafts so you don't email Diljit shows
        skipped = conn.execute(
            "SELECT id FROM events WHERE opportunity_tier='skip'"
        ).fetchall()
        for row in skipped:
            conn.execute(
                "DELETE FROM outreach WHERE target_type='event' AND target_id=? AND status='draft'",
                (row["id"],),
            )
            conn.execute("DELETE FROM matches WHERE event_id=? AND status='suggested'", (row["id"],))
    msg = (
        f"Rescored: {counts['chase']} chase · {counts['research']} research · "
        f"{counts['skip']} skipped (hidden)."
    )
    return RedirectResponse(f"/events?ok={quote(msg)}", status_code=303)


@app.post("/outreach/{outreach_id}/approve")
def approve_outreach(outreach_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT target_type FROM outreach WHERE id=?", (outreach_id,)).fetchone()
        page = _outreach_page_for(row["target_type"] if row else None)
        conn.execute(
            "UPDATE outreach SET founder_approved=1, status='approved' WHERE id=?",
            (outreach_id,),
        )
    return RedirectResponse(page, status_code=303)


@app.get("/deals", response_class=HTMLResponse)
def deals_page(request: Request):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.*, e.name AS event_name, b.name AS brand_name
            FROM deals d
            JOIN events e ON e.id = d.event_id
            JOIN brands b ON b.id = d.brand_id
            ORDER BY d.id DESC
            """
        ).fetchall()
    events = fetch_all("events")
    brands = fetch_all("brands")
    return templates.TemplateResponse(
        "deals.html",
        {
            "request": request,
            "deals": [dict(r) for r in rows],
            "events": events,
            "brands": brands,
        },
    )


@app.post("/deals")
def create_deal(
    event_id: int = Form(...),
    brand_id: int = Form(...),
    package_name: str = Form(...),
    deal_amount: int = Form(...),
    commission_pct: float = Form(15.0),
):
    commission_amount = calc_commission(deal_amount, commission_pct)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO deals (event_id, brand_id, package_name, deal_amount,
                commission_pct, commission_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, 'negotiating')
            """,
            (
                event_id,
                brand_id,
                package_name,
                deal_amount,
                commission_pct,
                commission_amount,
            ),
        )
    return RedirectResponse("/deals", status_code=303)


def _blithchron_rows(brands: list[dict], outreach_by_brand: dict) -> list[dict]:
    conf_tone = {
        "renew": "ok",
        "public_inbox": "ok",
        "named_public": "info",
        "local_public": "ok",
        "route_only": "warn",
    }
    rows = []
    for b in brands:
        notes = b.get("notes") or ""
        package = ask = ""
        if "Blithchron'27 |" in notes:
            parts = [p.strip() for p in notes.split("|")]
            if len(parts) >= 3:
                package = parts[1]
                ask = parts[2].replace("ask ", "")
        o = outreach_by_brand.get(b["id"])
        conf = "route_only"
        if "confidence=" in notes:
            conf = notes.split("confidence=")[1].split("|")[0].strip()
        pkg = package or b.get("category") or ""
        channels = enrich_channels(
            {
                "name": b["name"],
                "package": pkg,
                "ask_inr": ask,
                "contact_phone": b.get("contact_phone") or "",
                "contact_email": b.get("contact_email") or "",
                "phone": b.get("contact_phone") or "",
                "email": b.get("contact_email") or "",
            }
        )
        rows.append(
            {
                "brand": b,
                "package": pkg,
                "ask": ask,
                "confidence": conf,
                "confidence_tone": conf_tone.get(conf, "neutral"),
                "outreach_id": o["id"] if o else None,
                "outreach_status": (o or {}).get("status") or "",
                "channels": channels,
            }
        )
    rows.sort(
        key=lambda r: (
            0 if r["confidence"] == "renew" else 1 if r["confidence"] in ("public_inbox", "named_public", "local_public") else 2,
            0 if r["channels"]["has_wa"] else 1,
            r["brand"]["name"],
        )
    )
    return rows


@app.get("/blithchron", response_class=HTMLResponse)
def blithchron_page(request: Request):
    """Temporary dedicated desk for Blithchron '27 leads + bulk email + WhatsApp/LinkedIn."""
    with get_conn() as conn:
        brands = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM brands WHERE segment='blithchron27' ORDER BY conversion_tier DESC, name"
            ).fetchall()
        ]
        local_brands = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM brands WHERE segment='blithchron27_local' ORDER BY conversion_tier DESC, name"
            ).fetchall()
        ]
        outreach_by_brand = {}
        for r in conn.execute(
            "SELECT * FROM outreach WHERE agent_name IN ('blithchron27','blithchron27_local') ORDER BY id DESC"
        ).fetchall():
            r = dict(r)
            outreach_by_brand.setdefault(r["target_id"], r)

    rows = _blithchron_rows(brands, outreach_by_brand)
    local_rows = _blithchron_rows(local_brands, outreach_by_brand)

    emailable = sum(1 for r in rows if (r["brand"].get("contact_email") or "").strip())
    no_email = [r for r in rows if not (r["brand"].get("contact_email") or "").strip()]
    wa_national = [r for r in no_email if r["channels"]["has_wa"]]
    li_national = [r for r in no_email if not r["channels"]["has_wa"]]
    wa_local = [r for r in local_rows if r["channels"]["has_wa"]]
    email_local = sum(1 for r in local_rows if (r["brand"].get("contact_email") or "").strip())

    sendable = [
        r for r in rows
        if r["outreach_id"] and r["outreach_status"] != "sent" and (r["brand"].get("contact_email") or "").strip()
    ]
    sendable_local = [
        r for r in local_rows
        if r["outreach_id"] and r["outreach_status"] != "sent" and (r["brand"].get("contact_email") or "").strip()
    ]
    remaining = sum(1 for r in rows if r["outreach_status"] != "sent")
    sent_count = sum(1 for r in rows if r["outreach_status"] == "sent")
    sender = sender_profile()

    # Preload WA URLs for sequential opener (national no-email + local with phone)
    wa_queue = [
        {"name": r["brand"]["name"], "url": r["channels"]["wa_url"]}
        for r in (wa_national + wa_local)
        if r["channels"].get("wa_url")
    ]

    return templates.TemplateResponse(
        "blithchron.html",
        {
            "request": request,
            "rows": rows,
            "local_rows": local_rows,
            "no_email_rows": no_email,
            "wa_national": wa_national,
            "li_national": li_national,
            "wa_local": wa_local,
            "wa_queue": wa_queue,
            "total": len(rows),
            "local_total": len(local_rows),
            "emailable": emailable,
            "email_local": email_local,
            "no_email_count": len(no_email),
            "wa_count": len(wa_queue),
            "sendable_count": len(sendable),
            "sendable_local_count": len(sendable_local),
            "remaining": remaining,
            "sent_count": sent_count,
            "sender": sender,
            "gmail_ready": gmail_ready(),
            "flash_ok": request.query_params.get("ok", ""),
            "flash_err": request.query_params.get("err", ""),
        },
    )


@app.post("/blithchron/send-all")
def blithchron_send_all():
    with get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM outreach
                WHERE agent_name IN ('blithchron27','blithchron27_local') AND status!='sent'
                  AND ifnull(to_email,'') != ''
                ORDER BY id
                """
            ).fetchall()
        ]
        if not rows:
            return _outreach_redirect(
                error="No Blithchron drafts with email — use WhatsApp / LinkedIn queue on this page.",
                page="/blithchron",
            )
        try:
            sent_n, errors = send_many(rows)
        except MailerError as exc:
            return _outreach_redirect(error=str(exc), page="/blithchron")
        for item in rows:
            if item.get("_ok"):
                conn.execute(
                    """
                    UPDATE outreach
                    SET status='sent', founder_approved=1, sent_at=datetime('now'), send_error=''
                    WHERE id=?
                    """,
                    (item["id"],),
                )
            else:
                err = next((e for e in errors if str(item.get("to_email", "")) in e), "Send failed")
                conn.execute(
                    "UPDATE outreach SET send_error=? WHERE id=?",
                    (err[:400], item["id"]),
                )
    skipped = len(rows) - sent_n
    if sent_n and not skipped:
        return _outreach_redirect(f"Sent all {sent_n} Blithchron emails.", page="/blithchron")
    if sent_n:
        return _outreach_redirect(
            f"Sent {sent_n}. {skipped} failed — check send errors.",
            page="/blithchron",
        )
    return _outreach_redirect(
        error="Could not send. " + ("; ".join(errors[:2]) if errors else ""),
        page="/blithchron",
    )


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    return templates.TemplateResponse(
        "tasks.html", {"request": request, "tasks": fetch_all("founder_tasks")}
    )


@app.post("/tasks/{task_id}/done")
def complete_task(task_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE founder_tasks SET status='done', completed_at=datetime('now') WHERE id=?",
            (task_id,),
        )
    return RedirectResponse("/tasks", status_code=303)


# --- JSON API for agents / tests ---

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/founder-tasks/pending")
def pending_tasks():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM founder_tasks WHERE status='pending' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]
