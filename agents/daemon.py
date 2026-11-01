"""
Background agent team — runs while your laptop is on.

  python -m agents.daemon

Default: discovery + full team every 45 minutes (see data/discovery_config.json).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.discovery import load_config  # noqa: E402
from agents.orchestrator import log_run, run_daily  # noqa: E402


def main():
    cfg = load_config()
    interval = max(15, int(cfg.get("interval_minutes", 45))) * 60
    print(f"SponsorDesk agent daemon started. Cycle every {interval // 60} minutes.")
    print("Leave this window open while you work. Ctrl+C to stop.")

    while True:
        started = datetime.now(timezone.utc).isoformat()
        try:
            run_daily(include_discovery=True)
            log_run(
                "Daemon",
                "cycle",
                f"Completed discovery + agent team at {started}",
                1,
                [],
            )
        except Exception as exc:
            log_run("Daemon", "error", str(exc)[:500], 0, [])
            print(f"Cycle error: {exc}")
        print(f"Sleeping {interval // 60} min until next scan…")
        time.sleep(interval)


if __name__ == "__main__":
    main()
