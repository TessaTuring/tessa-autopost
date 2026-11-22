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

    # Two extra posts a day: a morning tip and an evening conversation starter (written by Claude).
    # If either fails, the main post still goes out.
    extras = {}
    for slot in ("am", "pm"):
        try:
            from threads_generate import generate

            recent = [h["topic"] for h in history] + [h["topic"] for h in load_history()]
            extra = generate(day.weekday(), recent, day.strftime("%A, %B %d"), slot=slot)
            rec = {"date": day.isoformat(), "slot": slot, "topic": extra["topic"], "text": extra["text"],
                   "source": "claude"}
            (THREADS / f"{day.isoformat()}-{slot}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
            history.append({"date": rec["date"], "topic": rec["topic"], "source": f"claude-{slot}"})
            extras[slot] = rec
        except Exception as e:  # noqa: BLE001
            print(f"::warning::Could not write the {slot} Threads post: {e}")
    THREADS_HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")

    origin = "from the reviewed library" if source == "library" else "written fresh by Claude"
    parts = [
        f"**Three Threads posts for {day.strftime('%A, %B %d')}** (times are Eastern).\n\n"
        "To skip all of them, just **close this issue**. Do nothing and they post automatically.\n"
    ]
    if "am" in extras:
        parts.append(f"### Around 8:30 AM: morning tip\n\n**Topic:** {extras['am']['topic']}\n\n```\n{extras['am']['text']}\n```\n")
    parts.append(f"### Around 11 AM: main post\n\n**Topic:** {post['topic']} ({origin})\n\n"
                 f"**Post** ({len(post['text'])} characters):\n\n```\n{post['text']}\n```\n")
    if "pm" in extras:
        parts.append(f"### Around 6 PM: evening question\n\n```\n{extras['pm']['text']}\n```\n")
    (THREADS / f"{day.isoformat()}.md").write_text("\n".join(parts))
    print(f"Drafted Threads post for {day}: {post['topic']} ({source})")


if __name__ == "__main__":
    main()
