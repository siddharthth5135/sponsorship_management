"""Data paths — local ./data or Render persistent disk via DATA_DIR."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    raw = (os.environ.get("DATA_DIR") or "").strip()
    p = Path(raw) if raw else (ROOT / "data")
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "brokerage.db"


def sender_profile_path() -> Path:
    return data_dir() / "sender_profile.json"
