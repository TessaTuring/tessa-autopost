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
    "the $9 AI Made Simple 7-day guided workbook (call it 'my AI Made Simple workbook' or 'my 7-day "
    "workbook'; large print, fill it in on screen or print it; never make results claims). What's inside: "
    "Day 1 getting set up and the privacy setting, Day 2 how to ask plus four phrases that fix any answer, "
    "Day 3 letters and forms explained, Day 4 bills and forgotten subscriptions, Day 5 notes, group chats "
    "and family moments, Day 6 appointment prep and learning gadgets step by step, Day 7 second opinions "
    "on strange messages and double-checking answers. Also a printable cheat sheet and a prompt notebook."
)
# Monday = 0. Offer days point softly to a product in the last sentence; growth days never do.
OFFERS = {
    0: "Free-guide day. In the last sentence, softly point to " + FREE_GUIDE + " Say it's in or linked from "
       "'my profile'. If you name a shortcut number, it must match this list.",
    3: "Free-guide day. In the last sentence, softly point to " + FREE_GUIDE + " Say it's in or linked from "
       "'my profile'. If you name a shortcut number, it must match this list.",
    2: "Workbook day. In the last sentence, softly point to " + PAID_PACK + " Name the ONE day or part that "
       "fits today's post, mention the $9 price, and say it's in or linked from 'my profile'.",
    4: "Workbook day. In the last sentence, softly point to " + PAID_PACK + " Name the ONE day or part that "
       "fits today's post, mention the $9 price, and say it's in or linked from 'my profile'.",
}
NO_OFFER = (
    "Growth day. Do not mention any guide, pack, product, profile or link. Write it so a reader wants to "
    "save it or send it to a friend, and end the post with ONE specific, easy question they can answer "
    "in a few words."
)

# Extra daily slots (3 posts a day): a morning tip and an evening conversation starter. Neither sells.
SLOT_BRIEFS = {
    "am": NO_OFFER + " This is the MORNING post: a practical tip with a copy-paste prompt that suits the start "
          "of someone's day. Use a different topic from today's main post.",
    "pm": "EVENING post. This one ignores the usual SHAPE: no prompt, no tip. Write ONE or two short, warm "
          "sentences that invite replies from this audience about their real life with phones, computers or AI "
          "(a light question, a this-or-that, or what they'd love a hand with). No product, profile, guide or "
          "link. 40 to 220 characters. End with a question mark.",
}
SHORT_MIN, SHORT_MAX = 40, 220

SYSTEM = f"""You write short, text-only Threads posts for Tessa Turing (@tessa_turing), whose tagline is
"Plain-English AI help for real life." Her audience is grown-ups, mostly 45 and older, who feel a step
behind on AI or didn't grow up with this kind of tech: parents of grown kids, grandparents, people
caring for an aging parent, retirees and people in the later part of their careers. Her voice is warm,
patient and clear, like a friend who explains it once, kindly, with no jargon. Never talk down to the
reader, and never treat age as a problem or a joke.

HOW IT SOUNDS: like a real person talking to a friend. Conversational, with contractions and full,
flowing sentences. No choppy fragments, no ALL CAPS, no hype words. When a step involves the app
itself (where to tap to upload a photo or use the microphone), say it plainly in a few words. Use free
tools people already have: ChatGPT, Claude, Gemini, or Meta AI (already inside WhatsApp and
Messenger); name ChatGPT first when naming one. For anything about suspicious messages, AI is only a
second opinion: tell readers to contact the company using the number on their card or its website.

SHAPE: an opening sentence or two with ONE concrete anchor (a specific email, bill, form, list,
letter or moment), then a short copy-paste prompt on its own paragraph that works in ChatGPT, Claude
or Gemini, with [square brackets] for the parts the reader fills in, then one or two sentences with a
practical tip for using it, then the ending required for the day. The prompt must be genuinely useful,
specific and correct.

VALUE BAR (most important): every post must teach something a regular person would NOT think of on
their own. "Ask AI for dinner ideas" or "ask AI to summarize this" is too basic and gets rejected.
Each post needs one non-obvious move, for example: uploading a photo or screenshot (a fridge, an
error code, a statement, a school schedule), having the AI make a real file (an .ics calendar file,
a spreadsheet formula, a Gmail search), voice mode (rehearsing a hard conversation, talking a reply
out loud), asking the AI to ask questions first, to argue against a plan, to grade a draft against a
standard it writes first, to catch what's vague or missing, or saving details once in custom
instructions. Keep it understandable for non-techies, and only describe features that really exist.

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


def validate(post: dict, weekday: int, slot: str = "main") -> dict:
    text = re.sub(r"[ \t]+\n", "\n", post["text"].strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    for pat, label in TELLS:
        m = re.search(pat, text, re.I | re.M)
        if m:
            raise InvalidPost(f"it contains {label}: {m.group(0)!r}. Rewrite that part as one plain true statement")
    lo, hi = (SHORT_MIN, SHORT_MAX) if slot == "pm" else (MIN_CHARS, MAX_CHARS)
    if not lo <= len(text) <= hi:
        raise InvalidPost(f"the post is {len(text)} characters; it must be {lo} to {hi}")
    low = text.lower()
    if weekday in OFFERS and slot == "main":
        if "profile" not in low:
            raise InvalidPost("today the post must softly point to the offer in 'my profile'")
        if weekday in (2, 4) and "$9" not in text:
            raise InvalidPost("today the post must mention the $9 workbook")
    else:
        if re.search(r"\bprofile\b|\bguide\b|\b(?:my|the|shortcuts|\$7) pack\b|\bworkbook\b|\$\d", low):
            raise InvalidPost("growth posts must not mention any product, guide or profile link")
        if not text.endswith("?") or text.count("?") > 2:
            raise InvalidPost("a growth post must end with one specific question")
    post["text"] = text
    post["topic"] = post["topic"].strip()
    return post


def generate(weekday: int, recent_topics: list[str], date_label: str, slot: str = "main") -> dict:
    client = anthropic.Anthropic()
    recent = "\n".join(f"- {t}" for t in recent_topics[-80:]) or "- (none yet)"
    user = (
        f"Write the Threads post for {date_label}.\n"
        f"Content pillar: {PILLARS[weekday]}\n"
        f"{SLOT_BRIEFS[slot] if slot in SLOT_BRIEFS else OFFERS.get(weekday, NO_OFFER)}\n\n"
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
            return validate(json.loads(text), weekday, slot)
        except (InvalidPost, json.JSONDecodeError) as e:
            last_err = str(e)
    raise InvalidPost(f"gave up after 4 attempts: {last_err}")
