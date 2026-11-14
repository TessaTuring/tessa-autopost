"""Ask Claude for one day's text-only Threads post and check it against Tessa's rules.

Only used once the reviewed library (content/threads_library.json) has no unused post left
for that weekday.
"""
from __future__ import annotations

import json
import re

import anthropic

from generate import MODEL, PILLARS

MIN_CHARS, MAX_CHARS = 280, 450  # Threads allows 500

FREE_GUIDE = (
    "the free 10 AI Shortcuts guide. Its 10 prompts: 1 Inbox triage, 2 Reply to anything fast, "
    "3 Say no without guilt, 4 Summarize a long thread, 5 One idea, five posts, 6 Brain dump to plan, "
    "7 Plan my day realistically, 8 Meeting notes to action items, 9 Spot subscriptions to cancel, "
    "10 Use what's in the fridge."
)
PAID_PACK = (
    "the $7 50 AI Shortcuts pack (call it 'my 50 AI Shortcuts pack' or 'my $7 shortcuts pack'; never "
    "use its full title or any time-saving claim). Sections and prompts: Email and messages (1 Reply to "
    "anything fast, 2 Say no without guilt, 3 Summarize a long thread, 4 Write the awkward follow-up, "
    "5 Fix my tone, 6 Ask for something clearly, 7 Turn notes into an update, 8 Calm down an angry email, "
    "9 Thank-you note that isn't generic, 10 Inbox triage); Writing and content (11 Teach it your voice, "
    "12 Beat the blank page, 13 Shorten anything, 14 One idea, five posts, 15 Better headlines, "
    "16 Explain it simply, 17 Edit like a pro, 18 Bio in every length, 19 Product description, "
    "20 Content ideas for a month); Planning and productivity (21 Brain dump to plan, 22 Plan my day "
    "realistically, 23 Break down a big project, 24 Find my top priority, 25 Run a better meeting, "
    "26 Meeting notes to action items, 27 Weekly review, 28 Checklist for anything I repeat, "
    "29 Stop procrastinating, 30 Plan a goal backwards); Research and learning (31 Explain it like a "
    "tutor, 32 Summarize anything long, 33 Compare options, 34 Learn a skill in 30 days, 35 Prepare for "
    "a conversation, 36 Find the holes in my idea, 37 Turn notes into flashcards, 38 Decode jargon, "
    "39 Get the other side, 40 Research starting point); Life admin and money (41 Meal plan and grocery "
    "list, 42 Use what's in the fridge, 43 Simple monthly budget, 44 Spot subscriptions to cancel, "
    "45 Write a complaint, 46 Negotiate a bill, 47 Plan a trip, 48 Cleaning routine, 49 Decode a "
    "confusing letter or bill, 50 Gift ideas)."
)
# Monday = 0. Offer days point softly to a product in the last sentence; growth days never do.
OFFERS = {
    0: "Free-guide day. In the last sentence, softly point to " + FREE_GUIDE + " Say it's in or linked from "
       "'my profile'. If you name a shortcut number, it must match this list.",
    3: "Free-guide day. In the last sentence, softly point to " + FREE_GUIDE + " Say it's in or linked from "
       "'my profile'. If you name a shortcut number, it must match this list.",
    2: "Paid-pack day. In the last sentence, softly point to " + PAID_PACK + " Name ONE real prompt or "
       "section from the list that fits today's post, mention the $7 price, and say it's in or linked "
       "from 'my profile'.",
    4: "Paid-pack day. In the last sentence, softly point to " + PAID_PACK + " Name ONE real prompt or "
       "section from the list that fits today's post, mention the $7 price, and say it's in or linked "
       "from 'my profile'.",
}
NO_OFFER = (
    "Growth day. Do not mention any guide, pack, product, profile or link. Write it so a reader wants to "
    "save it or send it to a friend, and end the post with ONE specific, easy question they can answer "
    "in a few words."
)

SYSTEM = f"""You write short, text-only Threads posts for Tessa Turing (@tessa_turing), whose tagline is
"I find the AI shortcuts so you don't have to." Her audience is busy everyday people (not techies)
who want copy-paste AI prompts that save time. Her voice is warm, clear, a little dry, never hypey.

HOW IT SOUNDS: like a real person talking to a friend. Conversational, with contractions and full,
flowing sentences. No choppy fragments, no ALL CAPS, no hype words. A stranger must instantly know
who it's for (busy people who want AI to take a chore off their plate).

SHAPE: an opening sentence or two with ONE concrete anchor (a specific email, bill, form, list,
letter or moment), then a short copy-paste prompt on its own paragraph that works in ChatGPT, Claude
or Gemini, with [square brackets] for the parts the reader fills in, then one or two sentences with a
practical tip for using it, then the ending required for the day. The prompt must be genuinely useful,
specific and correct.

Hard rules:
- {MIN_CHARS} to {MAX_CHARS} characters in total, including line breaks.
- No emoji, no hashtags, no links, no em or en dashes.
- ZERO contrast structures: no "it's not X, it's Y", "not just X but Y", "X isn't the problem, Y is",
  "no X, no Y, just Z", "less about X, more about Y", "rather than", "instead of", "stop X, start Y",
  and no "X is better than Y" comparisons. State only the true half of a point, once.
- No rhetorical triplets (two or four items are fine), no stacked one-line paragraphs, no "Here's the
  thing" or other drama openers, no tidy motivational ending. Never use journey, unlock, game-changer,
  delve, transform, empower, navigate, leverage or seamless.
- Never say or imply Tessa is AI, an AI creator, an AI character or AI-generated. The account
  discloses that separately. Never claim human-only experiences (no family, boss, commute, "I tried",
  places she went, things that happened to her). She may share opinions ("my favorite", "I like").
- No made-up statistics, no testimonials or "a reader told me", no income or results claims, no
  time-saved numbers, no fake urgency, no medical, legal or financial advice. Remind readers to keep
  private details (account numbers, passwords) out of prompts when it fits.
- Do not repeat a topic or opening from the "recently posted" list."""

SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}, "text": {"type": "string"}},
    "required": ["topic", "text"],
    "additionalProperties": False,
}

NEG = r"(?:\b(?:not|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|never|no)\b|n't\b)"
TELLS = [
    (NEG + r"[^.!?\n]{0,60}[.!?;,]\s+(?:and\s+)?(?:it's|it is|it (?:\w+ )?(?:just )?means|you're|you are|they're|this is|but|just|instead)\b", 'a "not X, it\'s Y" contrast'),
    (r"\bnot (?:just|only|merely)\b", '"not just X but Y"'),
    (r"\b(?:isn't|aren't|wasn't|weren't|doesn't mean)\b[^.!?\n]{1,50}[,.]\s*\w+(?:\s\w+)?\s+(?:is|are|was|means)\b", '"X isn\'t Y, Z is"'),
    (r"\b(?:no|not)\s+\w+(?:\s+\w+){0,3},\s*(?:no|not)\s+\w+", '"no X, no Y"'),
    (r"\bless (?:about )?[^.,!?]{1,40},\s*more\b|\brather than\b|\binstead of\b|\bbetter than\b|\bfaster than\b", "a contrast or comparison"),
    (r"\bstop\b[^.!?]{1,50}[.!?]\s+start\b", '"stop X, start Y"'),
    (r"\b(?:here's the thing|let's be honest|let that sink in|read that again|the truth is|the real \w+ is)\b", "a drama opener"),
    (r"\b(?:journey|navigat\w+|unlock\w*|game[- ]?changer|empower\w*|resilien\w+|transform\w*|thrive|delve|seamless\w*|leverage|supercharge\w*)\b", "a banned word"),
    (r"\b(?:ai[- ]?(?:creator|character|generated|influencer|persona)|i'?m an ai|i am an ai|as an ai)\b", "AI identity wording"),
    (r"\b(?:my (?:kids?|husband|wife|boss|mom|dad|partner|daughter|son|commute)|i tried|yesterday i|last week i|when i was)\b", "a human-only experience"),
    (r"\b(?:guarantee\w*|income|earn\w*|\d+ hours a week|today only|last chance|hurry)\b", "a claim or urgency"),
    (r"[–—]", "an em or en dash"),
    (r"(^|\s)#\w|https?://|www\.", "a hashtag or link"),
    (r"[\U0001F000-\U0001FAFF☀-➿️]", "an emoji"),
]


class InvalidPost(Exception):
    pass


def validate(post: dict, weekday: int) -> dict:
    text = re.sub(r"[ \t]+\n", "\n", post["text"].strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    for pat, label in TELLS:
        m = re.search(pat, text, re.I | re.M)
        if m:
            raise InvalidPost(f"it contains {label}: {m.group(0)!r}. Rewrite that part as one plain true statement")
    if not MIN_CHARS <= len(text) <= MAX_CHARS:
        raise InvalidPost(f"the post is {len(text)} characters; it must be {MIN_CHARS} to {MAX_CHARS}")
    low = text.lower()
    if weekday in OFFERS:
        if "profile" not in low:
            raise InvalidPost("today the post must softly point to the offer in 'my profile'")
        if weekday in (2, 4) and "$7" not in text:
            raise InvalidPost("today the post must mention the $7 pack")
    else:
        if re.search(r"\bprofile\b|\bguide\b|\b(?:my|the|shortcuts|\$7) pack\b|\$\d", low):
            raise InvalidPost("growth posts must not mention any product, guide or profile link")
        if not text.endswith("?") or text.count("?") > 2:
            raise InvalidPost("a growth post must end with one specific question")
    post["text"] = text
    post["topic"] = post["topic"].strip()
    return post


def generate(weekday: int, recent_topics: list[str], date_label: str) -> dict:
    client = anthropic.Anthropic()
    recent = "\n".join(f"- {t}" for t in recent_topics[-80:]) or "- (none yet)"
    user = (
        f"Write the Threads post for {date_label}.\n"
        f"Content pillar: {PILLARS[weekday]}\n"
        f"{OFFERS.get(weekday, NO_OFFER)}\n\n"
        f"Recently posted on Threads or Instagram (do not repeat):\n{recent}"
    )
    last_err = None
    for _ in range(4):
        content = user + (f"\n\nYour previous attempt was rejected: {last_err}. Fix that." if last_err else "")
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
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
            return validate(json.loads(text), weekday)
        except (InvalidPost, json.JSONDecodeError) as e:
            last_err = str(e)
    raise InvalidPost(f"gave up after 4 attempts: {last_err}")
