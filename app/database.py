import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.paths import db_path

DB_PATH: Path = db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    category TEXT NOT NULL,
    event_date TEXT,
    planning_stage TEXT DEFAULT 'planning',
    footfall_estimate INTEGER,
    packages_json TEXT DEFAULT '[]',
    organizer_name TEXT,
    organizer_phone TEXT,
    organizer_email TEXT,
    loi_signed INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    category TEXT NOT NULL,
    budget_min INTEGER DEFAULT 0,
    budget_max INTEGER DEFAULT 0,
    goal TEXT DEFAULT 'awareness',
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    past_sponsorships TEXT DEFAULT '',
    status TEXT DEFAULT 'prospect',
    notes TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    brand_id INTEGER NOT NULL,
    fit_score REAL DEFAULT 0,
    fit_tier TEXT DEFAULT 'partial',
    status TEXT DEFAULT 'suggested',
    organizer_approved INTEGER DEFAULT 0,
    intro_done INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    UNIQUE(event_id, brand_id)
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    channel TEXT DEFAULT 'email',
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    agent_name TEXT DEFAULT '',
    founder_approved INTEGER DEFAULT 0,
    sent_at TEXT,
    reply_status TEXT DEFAULT 'none',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    brand_id INTEGER NOT NULL,
    package_name TEXT NOT NULL,
    deal_amount INTEGER NOT NULL,
    commission_pct REAL DEFAULT 15,
    commission_amount INTEGER NOT NULL,
    status TEXT DEFAULT 'negotiating',
    invoice_sent INTEGER DEFAULT 0,
    payment_received INTEGER DEFAULT 0,
    closed_at TEXT,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    run_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    items_created INTEGER DEFAULT 0,
    founder_actions_json TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS founder_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'high',
    related_type TEXT,
    related_id INTEGER,
    status TEXT DEFAULT 'pending',
    due_date TEXT,
    created_by_agent TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
"""


DISCOVERIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_type TEXT NOT NULL,
    title TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    query_used TEXT DEFAULT '',
    why_chosen TEXT NOT NULL,
    status TEXT DEFAULT 'candidate',
    imported_table TEXT,
    imported_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_discoveries_url ON discoveries(source_url);
"""

COLUMN_MIGRATIONS = [
    ("events", "discovery_reason", "TEXT DEFAULT ''"),
    ("events", "description", "TEXT DEFAULT ''"),
    ("events", "date_label", "TEXT DEFAULT ''"),
    ("events", "audience", "TEXT DEFAULT ''"),
    ("events", "contact_role", "TEXT DEFAULT ''"),
    ("events", "website", "TEXT DEFAULT ''"),
    ("events", "linkedin_url", "TEXT DEFAULT ''"),
    ("brands", "discovery_reason", "TEXT DEFAULT ''"),
    ("brands", "description", "TEXT DEFAULT ''"),
    ("brands", "target_categories", "TEXT DEFAULT ''"),
    ("brands", "contact_role", "TEXT DEFAULT ''"),
    ("brands", "website", "TEXT DEFAULT ''"),
    ("brands", "linkedin_url", "TEXT DEFAULT ''"),
    ("brands", "conversion_tier", "TEXT DEFAULT 'possible'"),
    ("brands", "intent_signal", "TEXT DEFAULT 'latent'"),
    ("brands", "segment", "TEXT DEFAULT ''"),
    ("matches", "match_reason", "TEXT DEFAULT ''"),
    ("outreach", "to_name", "TEXT DEFAULT ''"),
    ("outreach", "to_email", "TEXT DEFAULT ''"),
    ("outreach", "from_email", "TEXT DEFAULT ''"),
    ("outreach", "send_error", "TEXT DEFAULT ''"),
    ("events", "opportunity_score", "REAL DEFAULT 0"),
    ("events", "opportunity_tier", "TEXT DEFAULT 'research'"),
    ("events", "opportunity_reason", "TEXT DEFAULT ''"),
]


def init_db() -> None:
    global DB_PATH
    DB_PATH = db_path()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(DISCOVERIES_SCHEMA)
        for table, column, decl in COLUMN_MIGRATIONS:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


@contextmanager
def get_conn():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


TABLES_CLEAR_ORDER = [
    "founder_tasks",
    "agent_runs",
    "outreach",
    "deals",
    "matches",
    "discoveries",
    "brands",
    "events",
]


def clear_all_data() -> None:
    """Remove all rows — production go-live with empty CRM."""
    init_db()
    with get_conn() as conn:
        for table in TABLES_CLEAR_ORDER:
            conn.execute(f"DELETE FROM {table}")
        try:
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ({})".format(
                    ",".join(f"'{t}'" for t in TABLES_CLEAR_ORDER)
                )
            )
        except sqlite3.OperationalError:
            pass
