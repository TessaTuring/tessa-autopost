"""Write today's 15-minute engagement list (searches to open + starter replies) as a GitHub issue body.

Nothing is posted automatically: a person reads the list and replies in their own words.

Usage: python scripts/engage.py [YYYY-MM-DD]   -> writes engage/<date>.md
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.parse

import anthropic

from common import DRAFTS, ROOT, today_et
from generate import MODEL
from threads_generate import TELLS

OUT = ROOT / "engage"

SYSTEM = """You help a social media manager grow Tessa Turing, a creator who gives plain-English AI help
for real life to grown-ups (mostly 45 and older) who feel a step behind on AI. Each morning you plan 15
minutes of genuine, helpful engagement on OTHER people's posts and groups, where this audience already is.

Pick search terms that surface conversations where Tessa's help fits naturally: people asking how to use
ChatGPT, feeling overwhelmed by tech, dealing with confusing letters or bills, caring for aging parents,
retirement life, grandparents keeping up with family tech, and today's topic. Prefer Facebook groups and
Facebook posts (this audience lives there), then Threads, then Instagram hashtags.

Starter replies are drafts a human will reword. Each one: 1 to 3 warm, specific sentences that give a real
piece of help (a mini tip or a short prompt idea), sound like a friendly person, never sell, never include
links, never mention Tessa's products, profile or guide, never say "follow me", never claim to be AI or
mention being an AI creator, and never claim human experiences (no family, "I tried", places).
No emoji, no hashtags, no em or en dashes, no contrast structures ("not X, it's Y", "rather than",
"instead of"), no rhetorical triplets, and none of: journey, unlock, game-changer, delve, transform,
empower, navigate, leverage, seamless."""

SCHEMA = {
    "type": "object",
    "properties": {
        "searches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "enum": ["Facebook groups", "Facebook posts", "Threads",
                                                             "Instagram hashtag"]},
                    "query": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["platform", "query", "why"],
                "additionalProperties": False,
            },
        },
        "replies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"when": {"type": "string"}, "reply": {"type": "string"}},
                "required": ["when", "reply"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["searches", "replies"],
    "additionalProperties": False,
}


def url(platform: str, query: str) -> str:
    q = urllib.parse.quote(query)
    if platform == "Facebook groups":
        return f"https://www.facebook.com/search/groups/?q={q}"
    if platform == "Facebook posts":
        return f"https://www.facebook.com/search/posts/?q={q}"
    if platform == "Threads":
        return f"https://www.threads.com/search?q={q}&serp_type=default"
    tag = re.sub(r"[^a-z0-9]", "", query.lower())
    return f"https://www.instagram.com/explore/tags/{tag}/"


def check(plan: dict) -> dict:
    if len(plan["searches"]) < 4 or len(plan["replies"]) < 4:
        raise ValueError("give at least 4 searches and at least 4 replies")
    for r in plan["replies"]:
        text = r["reply"]
        if len(text) > 320:
            raise ValueError(f"a reply is too long ({len(text)} characters); keep each under 320")
        if re.search(r"https?://|www\.|\bprofile\b|\bguide\b|\bworkbook\b|\bfollow me\b|\$\d", text, re.I):
            raise ValueError(f"a reply sells or links: {text[:60]!r}")
        for pat, label in TELLS:
            m = re.search(pat, text, re.I | re.M)
            if m:
                raise ValueError(f"a reply contains {label}: {m.group(0)!r}")
    return plan


def make_plan(day: dt.date) -> dict:
    topics = []
    post = DRAFTS / day.isoformat() / "post.json"
    if post.exists():
        topics.append(json.loads(post.read_text())["topic"])
    th = ROOT / "threads" / f"{day.isoformat()}.json"
    if th.exists():
        topics.append(json.loads(th.read_text())["topic"])
    client = anthropic.Anthropic()
    user = (f"Plan today's engagement for {day.strftime('%A, %B %d')}. Tessa's posts today are about: "
            f"{'; '.join(topics) or 'everyday AI help'}.\nGive 5 searches and 5 starter replies.")
    last = None
    for _ in range(4):
        content = user + (f"\n\nYour previous attempt was rejected: {last}. Fix that." if last else "")
        resp = client.beta.messages.create(
            model=MODEL, max_tokens=4000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            system=SYSTEM, messages=[{"role": "user", "content": content}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        if resp.stop_reason in ("refusal", "max_tokens"):
            last = "try again with a shorter, everyday plan"
            continue
        try:
            return check(json.loads(next(b.text for b in resp.content if b.type == "text")))
        except (ValueError, json.JSONDecodeError) as e:
            last = str(e)
    raise RuntimeError(f"gave up: {last}")


def main() -> None:
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today_et()
    plan = make_plan(day)
    lines = [
        f"**Your 15 minutes for {day.strftime('%A, %B %d')}.** Signed in as Tessa, reply in your own words. "
        "No links, no selling: helpful replies make people click her profile on their own.\n",
        "### 1. Reply to everyone who commented on Tessa (5 min)\n",
        "- [Instagram activity](https://www.instagram.com/accounts/activity/)",
        "- [Threads activity](https://www.threads.com/activity)",
        "- [Facebook page notifications](https://www.facebook.com/tessaturing/notifications)\n",
        "### 2. Find 5 conversations to help in (10 min)\n",
    ]
    for s in plan["searches"]:
        lines.append(f"- [ ] **{s['platform']}:** [{s['query']}]({url(s['platform'], s['query'])}): {s['why']}")
    lines.append("\n### Starter replies (reword before posting)\n")
    for r in plan["replies"]:
        lines.append(f"- **When someone {r['when'].rstrip('.')}:**\n  > {r['reply']}")
    lines.append("\nClose this issue when you're done. A new list arrives every morning.")
    OUT.mkdir(exist_ok=True)
    (OUT / f"{day.isoformat()}.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote engagement list for {day}")


if __name__ == "__main__":
    main()
