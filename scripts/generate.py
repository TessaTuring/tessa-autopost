"""Ask Claude for one day's carousel and validate it against Tessa's content rules."""
from __future__ import annotations

import json
import re

import anthropic

MODEL = "claude-opus-5-5"

# Content pillars rotate by weekday (Monday = 0) so the feed stays varied.
PILLARS = [
    "Email and messages",
    "Planning and productivity",
    "Writing and content",
    "Life admin and money (budgets, bills, subscriptions; general tips only, never financial advice)",
    "Research and learning",
    "Home and everyday life (meals, cleaning, trips, gifts)",
    "Weekly reset (reviews, routines, planning the week ahead)",
]

# Candid, medium-wide cover photos of Tessa busy at her desk (never posed at the camera).
COVER_MOODS = ["laptop", "notebook", "coffee", "phone", "planner", "reading", "thinking", "weekend"]
# laptop: typing on a laptop | notebook: writing by hand | coffee: leaning back with a mug
# phone: smiling at her phone | planner: planning with sticky notes | reading: curled up with a book
# thinking: reading her screen, chin on hand | weekend: closing the laptop, done for the day

SYSTEM = """You write Instagram carousels for Tessa Turing, a creator whose tagline is
"I find the AI shortcuts so you don't have to." Her audience is busy everyday people (not
techies) who want copy-paste AI prompts that save time. Her voice is warm, clear, a little
dry, never hypey.

Every carousel teaches ONE practical, specific shortcut or a tight set of related prompts that
work in ChatGPT, Claude or Gemini (free versions). The reader should be able to copy a prompt
from the slide and use it in under a minute.

Structure (5 to 8 slides total):
1. One "cover" slide: a scroll-stopping hook title (max 55 characters) and a short subtitle
   (max 45 characters). Pick the cover photo that best fits the topic: laptop (typing), notebook (writing by hand),
   coffee (relaxed with a mug), phone (on her phone), planner (planning/organizing), reading (with a book),
   thinking (reading her screen), weekend (closing the laptop, wrap-up or reset topics).
2. 3 to 6 middle slides of type "text" or "prompt". Prompt slides carry one copy-paste prompt
   with [square brackets] for the parts the reader fills in. Use text slides for a problem
   setup, a before/after example, or a tip.
3. One final "cta" slide inviting the reader to save the post and grab the free guide
   (10 AI Shortcuts) via the link in bio.

Hard rules:
- Slide text must not contain emoji or special symbols (they cannot be rendered). Captions may.
- Never say or imply Tessa is AI, an AI creator, an AI character, or AI-generated. The account
  discloses that separately. Also never claim human-only experiences (no "my kids", "my boss",
  "I cooked", personal income, places she went).
- No made-up statistics, no income or results claims, no medical, legal or financial advice.
- Prompts must be genuinely useful, specific and correct. No filler slides.
- Keep slide text short: titles max 60 characters, body max 200 characters, prompts max 260.
- Do not repeat a topic or hook from the "recently posted" list.
- Caption: a hook line, 2 to 4 short lines explaining the tip, a save reminder, a pointer to
  the free guide in bio, then 4 or 5 relevant lowercase hashtags (in the hashtags field, not
  in the caption text)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "cover_title": {"type": "string"},
        "cover_subtitle": {"type": "string"},
        "cover_mood": {"type": "string", "enum": COVER_MOODS},
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["text", "prompt", "cta"]},
                    "kicker": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "prompt": {"type": "string"},
                },
                "required": ["type", "kicker", "title", "body", "prompt"],
                "additionalProperties": False,
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "cover_title", "cover_subtitle", "cover_mood", "slides", "caption", "hashtags"],
    "additionalProperties": False,
}

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U0000FE0F\U0000200D\U00002B00-\U00002BFF]"
)
BANNED = re.compile(r"\b(ai[- ]creator|ai[- ]character|ai[- ]generated|i'?m an ai|i am an ai)\b", re.I)


class InvalidPost(Exception):
    pass


def validate(post: dict) -> dict:
    mids = [s for s in post["slides"] if s["type"] in ("text", "prompt")]
    ctas = [s for s in post["slides"] if s["type"] == "cta"]
    if not (3 <= len(mids) <= 6):
        raise InvalidPost(f"expected 3-6 middle slides, got {len(mids)}")
    if len(ctas) != 1 or post["slides"][-1]["type"] != "cta":
        raise InvalidPost("exactly one cta slide, last")
    if not any(s["type"] == "prompt" and s["prompt"].strip() for s in mids):
        raise InvalidPost("needs at least one prompt slide")

    limits = {"title": 70, "body": 230, "prompt": 290, "kicker": 40}
    for s in post["slides"]:
        for k, lim in limits.items():
            s[k] = EMOJI.sub("", s[k]).strip()
            if len(s[k]) > lim:
                raise InvalidPost(f"{k} too long ({len(s[k])}>{lim}): {s[k][:40]}...")
    post["cover_title"] = EMOJI.sub("", post["cover_title"]).strip()
    post["cover_subtitle"] = EMOJI.sub("", post["cover_subtitle"]).strip()
    if len(post["cover_title"]) > 70:
        raise InvalidPost("cover title too long")

    all_text = json.dumps(post)
    if BANNED.search(all_text):
        raise InvalidPost("mentions AI identity")
    post["hashtags"] = [("#" + h.lstrip("#")).lower().replace(" ", "") for h in post["hashtags"]][:5]
    return post


def generate(pillar: str, recent_topics: list[str], date_label: str) -> dict:
    client = anthropic.Anthropic()
    recent = "\n".join(f"- {t}" for t in recent_topics[-60:]) or "- (none yet)"
    user = (
        f"Write the carousel for {date_label}.\n"
        f"Today's content pillar: {pillar}\n\n"
        f"Recently posted (do not repeat):\n{recent}"
    )
    last_err = None
    for attempt in range(3):
        msgs = [{"role": "user", "content": user}]
        if last_err:
            msgs[0]["content"] += f"\n\nYour previous attempt was rejected: {last_err}. Fix that."
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=msgs,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        if resp.stop_reason == "refusal":
            last_err = "the request was declined; pick a different, everyday topic"
            continue
        if resp.stop_reason == "max_tokens":
            last_err = "the answer was cut off; keep it shorter"
            continue
        text = next(b.text for b in resp.content if b.type == "text")
        try:
            return validate(json.loads(text))
        except (InvalidPost, json.JSONDecodeError) as e:
            last_err = str(e)
    raise InvalidPost(f"gave up after 3 attempts: {last_err}")
