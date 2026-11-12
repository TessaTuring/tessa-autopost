from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
HISTORY = ROOT / "content" / "history.json"
TZ = ZoneInfo("America/New_York")


def today_et() -> dt.date:
    return dt.datetime.now(TZ).date()


def raw_url(rel_path: str) -> str:
    """Public URL of a committed file (the repo must be public for Instagram to fetch it)."""
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel_path}"


def load_history() -> list[dict]:
    return json.loads(HISTORY.read_text()) if HISTORY.exists() else []


def save_history(items: list[dict]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")


def issue_title(day: dt.date) -> str:
    return f"Post for {day.isoformat()}"
