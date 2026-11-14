"""Nightly: pick tomorrow's text-only Threads post and write the review-issue body.

Library first: the next unused reviewed post for that weekday in content/threads_library.json.
When the library has none left for that weekday, Claude writes a fresh one.

Usage: python scripts/threads_draft.py [YYYY-MM-DD]   (defaults to tomorrow, US Eastern)
Outputs threads/<date>.json and threads/<date>.md
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from common import ROOT, load_history, today_et

THREADS = ROOT / "threads"
THREADS_HISTORY = ROOT / "content" / "threads_history.json"
LIBRARY = ROOT / "content" / "threads_library.json"


def next_from_library(weekday: int, used: set[str]) -> dict | None:
    if not LIBRARY.exists():
        return None
    for post in json.loads(LIBRARY.read_text()):
        if post["weekday"] == weekday and post["topic"] not in used:
            return {"topic": post["topic"], "text": post["text"]}
    return None


def main() -> None:
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today_et() + dt.timedelta(days=1)
    THREADS.mkdir(exist_ok=True)
    out = THREADS / f"{day.isoformat()}.json"
    if out.exists():
        print(f"Threads draft for {day} already exists; nothing to do.")
        return

    history = json.loads(THREADS_HISTORY.read_text()) if THREADS_HISTORY.exists() else []
    post = next_from_library(day.weekday(), {h["topic"] for h in history})
    source = "library"
    if post is None:
        from threads_generate import generate  # only needs the Claude API when the library runs out

        source = "claude"
        recent = [h["topic"] for h in history] + [h["topic"] for h in load_history()]
        post = generate(day.weekday(), recent, day.strftime("%A, %B %d"))

    record = {"date": day.isoformat(), "topic": post["topic"], "text": post["text"], "source": source}
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    history.append({"date": record["date"], "topic": record["topic"], "source": source})
    THREADS_HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")

    origin = "from the reviewed library" if source == "library" else "written fresh by Claude"
    (THREADS / f"{day.isoformat()}.md").write_text(
        f"**Scheduled to post on Threads {day.strftime('%A, %B %d')} around 11 AM Eastern.**\n\n"
        f"To skip it, just **close this issue**. Do nothing and it posts automatically.\n\n"
        f"**Topic:** {post['topic']} ({origin})\n\n**Post** ({len(post['text'])} characters):\n\n"
        f"```\n{post['text']}\n```\n"
    )
    print(f"Drafted Threads post for {day}: {post['topic']} ({source})")


if __name__ == "__main__":
    main()
