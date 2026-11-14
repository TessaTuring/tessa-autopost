"""Nightly: write tomorrow's carousel, render it, and write the review-issue body.

Usage: python scripts/draft.py [YYYY-MM-DD]   (defaults to tomorrow, US Eastern)
Outputs drafts/<date>/{01..NN}.jpg, post.json, issue.md
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from common import DRAFTS, ROOT, load_history, raw_url, save_history, today_et
from generate import PERSONAS, PILLARS, TOOLS_PILLAR, generate
from render import render


def main() -> None:
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today_et() + dt.timedelta(days=1)
    out = DRAFTS / day.isoformat()
    if (out / "post.json").exists():
        print(f"Draft for {day} already exists; nothing to do.")
        return

    history = load_history()
    pillar = PILLARS[day.weekday()]
    persona = None
    if day.weekday() == 4:  # Fridays: AI tool picks for one kind of person, rotating weekly
        pillar = TOOLS_PILLAR
        persona = PERSONAS[((day - dt.date(2026, 11, 20)).days // 7) % len(PERSONAS)]
    post = generate(pillar, [h["topic"] for h in history], day.strftime("%A, %B %d"), persona)

    # Avoid reusing the same cover photo two days in a row.
    mood = post["cover_mood"]
    if history and history[-1].get("cover_mood") == mood:
        from generate import COVER_MOODS

        mood = COVER_MOODS[(COVER_MOODS.index(mood) + 1) % len(COVER_MOODS)]
    cover_slide = {"type": "cover", "title": post["cover_title"], "subtitle": post["cover_subtitle"]}
    if mood == "graphic":
        cover_slide["kicker"] = f"AI tools for {persona}" if persona else "AI shortcut"
    else:
        cover_slide["photo"] = f"assets/covers/{mood}.jpg"
    slides = [
        cover_slide,
        *post["slides"],
    ]
    paths = render(slides, out)

    caption = post["caption"].rstrip() + "\n\n" + " ".join(post["hashtags"])
    record = {
        "date": day.isoformat(),
        "topic": post["topic"],
        "pillar": pillar,
        "cover_mood": mood,
        "caption": caption,
        "images": [p.relative_to(ROOT).as_posix() for p in paths],
    }
    (out / "post.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    history.append({"date": record["date"], "topic": record["topic"], "cover_mood": mood})
    save_history(history)

    imgs = "\n".join(f'<img src="{raw_url(p)}" width="260">' for p in record["images"])
    (out / "issue.md").write_text(
        f"**Scheduled to post {day.strftime('%A, %B %d')} at 8 AM Eastern.**\n\n"
        f"To skip it, just **close this issue**. Do nothing and it posts automatically.\n\n"
        f"**Topic:** {post['topic']}\n\n{imgs}\n\n**Caption:**\n\n```\n{caption}\n```\n"
    )
    print(f"Drafted {day}: {post['topic']} ({len(paths)} slides)")


if __name__ == "__main__":
    main()
