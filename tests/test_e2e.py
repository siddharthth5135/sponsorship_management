import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Use isolated DB for tests
TEST_DB = Path(tempfile.gettempdir()) / "brokerage_test.db"
os.environ["BROKERAGE_TEST"] = "1"


@pytest.fixture()
def client(monkeypatch):
    import app.database as db

    monkeypatch.setattr(db, "DB_PATH", TEST_DB)
    if TEST_DB.exists():
        TEST_DB.unlink()
    db.init_db()

    from app.main import app

    with TestClient(app) as c:
        yield c


def _seed(client):
    for name in ("Fest One", "Fest Two"):
        client.post(
            "/events",
            data={
                "name": name,
                "city": "Ahmedabad",
                "category": "College cultural fest",
                "event_date": "2099-01-01",
                "planning_stage": "seeking_sponsors",
                "footfall_estimate": "12000",
                "organizer_email": f"{name.split()[1].lower()}@fest.test",
            },
        )
    client.post(
        "/brands",
        data={
            "name": "Snack Co",
            "city": "Ahmedabad",
            "category": "FMCG",
            "goal": "sampling",
            "contact_email": "hello@snack.test",
            "target_categories": ["College cultural fest", "Marathon / sports"],
        },
    )


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_matches_grouped_by_brand(client):
    _seed(client)
    r = client.post("/matches/run", follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/matches").text
    assert page.count('class="card card-flush brand-group"') == 1
    assert "Fest One" in page and "Fest Two" in page
    assert "2 events" in page


def test_outreach_drafts_have_recipients_and_dedupe(client):
    from agents.orchestrator import run_daily

    _seed(client)
    run_daily(include_discovery=False)
    run_daily(include_discovery=False)

    import app.database as db

    with db.get_conn() as conn:
        drafts = [dict(r) for r in conn.execute("SELECT * FROM outreach").fetchall()]
        dup_tasks = conn.execute(
            "SELECT title, COUNT(*) c FROM founder_tasks GROUP BY title HAVING c > 1"
        ).fetchall()
    assert len(drafts) == 3  # 2 organizers + 1 brand
    assert not dup_tasks
    assert all(d["from_email"] == "siddharththpatel@gmail.com" for d in drafts)
    brand_draft = next(d for d in drafts if d["target_type"] == "brand")
    assert brand_draft["to_email"] == "hello@snack.test"
    assert "no charge from us" in brand_draft["body"].lower() or "no brokerage" in brand_draft["body"].lower()
    assert "this week" in brand_draft["body"].lower()
    assert "Fest One" not in brand_draft["body"]
    assert "conversion fee" not in brand_draft["body"].lower()

    assert client.get("/outreach", follow_redirects=False).status_code == 303
    events_page = client.get("/outreach/events").text
    brands_page = client.get("/outreach/brands").text
    assert "Event outreach" in events_page
    assert "Brand outreach" in brands_page
    assert "hello@snack.test" in brands_page
    assert "mail.google.com" in brands_page or "mail.google.com" in events_page
    assert "Remaining" in events_page


def test_deal_commission(client):
    client.post("/events", data={"name": "E1", "city": "X", "category": "Marathon / sports"})
    client.post("/brands", data={"name": "B1", "city": "X", "category": "Sports"})
    client.post(
        "/deals",
        data={
            "event_id": "1",
            "brand_id": "1",
            "package_name": "Gold",
            "deal_amount": "100000",
            "commission_pct": "15",
        },
    )
    page = client.get("/deals")
    assert b"15,000" in page.content or b"15000" in page.content


def test_discovery_filters_junk():
    from agents.discovery import is_junk

    assert is_junk("Top 10 sponsors in India", "https://blog.example.com")
    assert is_junk("Sponsor events", "https://www.sponsormyevent.com/x")
    assert not is_junk("Amalthea '26 — Call for Sponsors", "https://www.linkedin.com/posts/amalthea")


def test_fee_wording_and_reach_channels(client):
    from app.services.emails import brand_email, organizer_email
    from app import ui

    subject, body = organizer_email(
        {
            "name": "Test Fest",
            "organizer_name": "Team",
            "audience": "students",
            "planning_stage": "seeking_sponsors",
        }
    )
    assert "nominal conversion fee for facilitating the sponsorship" in body
    assert "10–15%" not in body

    b_subject, b_body = brand_email({"name": "Local Cafe", "segment": "cafe"})
    assert "no fee" in b_subject.lower() or "no charge" in b_body.lower()
    assert "no brokerage" in b_body.lower() or "no charge from us" in b_body.lower()
    assert "15-minute" in b_body
    assert "conversion fee" not in b_body.lower()
    assert b_body.lower().count("?") <= 3
    assert "Upcoming events that fit" not in b_body

    channels = ui.reach_channels(
        "",
        "",
        "https://www.linkedin.com/in/example",
        "https://example.com",
        "https://www.linkedin.com/posts/example",
    )
    labels = [c["label"] for c in channels]
    assert "LinkedIn" in labels
    assert "Website" in labels

    page = client.get("/outreach/events").text
    assert "Send automatically" in page or "Gmail App Password" in page
    assert "Gmail auto-send" in page
    assert "Event outreach" in page


def test_orchestrator_daily():
    import app.database as db

    db.DB_PATH = TEST_DB
    if TEST_DB.exists():
        TEST_DB.unlink()
    from agents.orchestrator import run_daily

    run_daily(include_discovery=False)
    with db.get_conn() as conn:
        runs = conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
        tasks = conn.execute("SELECT COUNT(*) FROM founder_tasks").fetchone()[0]
    assert runs >= 6
    assert tasks >= 1
