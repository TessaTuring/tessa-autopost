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

# Cover options. Photo covers are candid, medium-wide shots in a bright, modern work-from-home
# setting (Tessa busy, never posing at the camera). Some covers have no Tessa at all.
# Only covers whose photo exists in assets/covers/ are offered; "graphic" needs no photo.
COVERS = {
    "graphic": "no photo, a clean bright text-only design (best for tool roundups and lists; use it for about 1 in 3 posts)",
    "flatlay": "no person, an overhead shot of a bright desk with laptop, phone and iced coffee (planning, writing, tools)",
    "desk": "Tessa typing at her bright home-office desk with an iced coffee (email, writing, work, planning, productivity)",
    "call": "Tessa on a video call at her desk with earbuds (meetings, work, research)",
    "phone": "Tessa leaning back in her desk chair, smiling at her phone with an iced coffee (texts, messages, quick tips)",
    "kitchen": "Tessa at a bright kitchen counter with her laptop and phone (meals, home, errands, money)",
    "sofa": "Tessa on the sofa with her laptop (evening inbox, weekend, learning)",
    "done": "Tessa closing her laptop with a smile, done for the day (weekly reset, wrap-ups)",
}
COVER_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "assets" / "covers"
COVER_MOODS = [m for m in COVERS if m == "graphic" or (COVER_DIR / f"{m}.jpg").exists()]

# Fridays: a roundup of AI tools for one kind of person. Only these tools may be named, and only
# for what is written here (no prices, no "free" claims, no claims that Tessa tested them).
TOOLS = {
    "ChatGPT": "general AI assistant for writing, planning, brainstorming and questions",
    "Claude": "AI assistant that is good with long documents, writing and summarizing files",
    "Gemini": "Google's AI assistant, also built into Gmail, Docs and other Google apps",
    "Microsoft Copilot": "Microsoft's AI assistant in Windows, Edge and Microsoft 365 apps like Word and Outlook",
    "Perplexity": "AI search that answers questions and shows the sources it used",
    "NotebookLM": "Google tool where you upload your own documents and ask questions about them or get summaries",
    "Canva": "design app with AI features for social posts, flyers and presentations",
    "Grammarly": "checks spelling, grammar and tone as you write in most apps",
    "Otter.ai": "records and transcribes meetings and makes notes from them",
    "Fathom": "AI notetaker that joins video calls and writes a summary",
    "Gamma": "turns an outline or notes into a slide deck or document with AI",
    "Notion AI": "AI inside Notion for notes, docs, to-do lists and summaries",
    "Goblin.tools": "small free-standing tools, including one that breaks a task into tiny steps",
    "CapCut": "video editor with automatic captions and quick AI edits",
    "Descript": "edit audio and video by editing the transcript like a document",
    "Zapier": "connects apps so routine steps happen automatically",
    "Reclaim.ai": "AI calendar helper that finds time for tasks and habits around meetings",
    "Motion": "AI planner that schedules your tasks into your calendar",
    "ElevenLabs": "AI voice tool for voiceovers and reading text aloud",
    "Khanmigo": "Khan Academy's AI tutor and teaching assistant",
}
PERSONAS = [
    "stay-at-home parents",
    "small business owners",
    "remote employees",
    "college students",
    "teachers",
    "freelancers",
    "job seekers",
    "people with a side hustle",
    "new managers",
    "retirees and anyone new to AI",
    "busy caregivers",
    "real estate agents",
]
TOOLS_PILLAR = "AI tool picks for one kind of person"

SYSTEM = """You write Instagram carousels for Tessa Turing, a creator whose tagline is
"I find the AI shortcuts so you don't have to." Her audience is busy everyday people (not
techies) who want copy-paste AI prompts that save time. Her voice is warm, clear, a little
dry, never hypey.

Every carousel teaches ONE practical, specific shortcut or a tight set of related prompts that
work in ChatGPT, Claude or Gemini (free versions). The reader should be able to copy a prompt
from the slide and use it in under a minute.

Structure (5 to 8 slides total):
1. One "cover" slide: a scroll-stopping hook title (max 55 characters) and a short subtitle
   (max 45 characters). Pick the cover that best fits the topic (cover_mood) from this list:
{covers}
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
- ZERO contrast structures anywhere in the slides or caption: no "it's not X, it's Y", "not just X
  but Y", "X is the easy part, Y is what gets you", "X isn't the problem, Y is", "no X, no Y, just Z",
  "less about X, more about Y", "rather than", "instead of", "stop X, start Y". State only the true
  half of a point, once. Also no "Here's the thing" style openers, no tidy motivational endings, and
  never use journey, unlock, game-changer, delve, transform, empower, navigate, leverage or seamless.
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


# Sentence shapes that read as machine-written (contrastive reveals and friends), checked on slide
# text and the caption. Prompts are skipped because instructions like "Don't ..." are fine there.
NEG = r"(?:\b(?:not|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|never|no)\b|n't\b)"
TELLS = [
    (NEG + r"[^.!?\n]{0,60}[.!?;,]\s+(?:and\s+)?(?:it's|it is|it (?:\w+ )?(?:just )?means|you're|you are|they're|this is|but|just|instead)\b", 'a "not X, it\'s Y" contrast'),
    (r"\bnot (?:just|only|merely)\b", '"not just X but Y"'),
    (r"\b(?:isn't|aren't|wasn't|weren't|doesn't mean)\b[^.!?\n]{1,50}[,.]\s*\w+(?:\s\w+)?\s+(?:is|are|was|means)\b", '"X isn\'t Y, Z is"'),
    (r"\b(?:no|not)\s+\w+(?:\s+\w+){0,3},\s*(?:no|not)\s+\w+", '"no X, no Y"'),
    (r"\bless (?:about )?[^.,!?]{1,40},\s*more\b|\brather than\b|\binstead of\b", "a contrast"),
    (r"\bthe easy part\b|\bthe hard part\b|\bwhat (?:really )?gets you\b", 'an "easy part / hard part" contrast'),
    (r"\bstop\b[^.!?]{1,50}[.!?]\s+start\b", '"stop X, start Y"'),
    (r"\b(?:here's the thing|let's be honest|let that sink in|read that again|the truth is|the real \w+ is)\b", "a drama opener"),
    (r"\b(?:journey|navigat\w+|unlock\w*|game[- ]?changer|empower\w*|transform\w*|delve|seamless\w*|leverage)\b", "a banned word"),
]


def find_tell(text: str) -> str | None:
    for pat, label in TELLS:
        m = re.search(pat, text, re.I | re.M)
        if m:
            return f"{label} ({m.group(0)!r})"
    return None


class InvalidPost(Exception):
    pass


def validate(post: dict, roundup: bool = False) -> dict:
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

    if post["cover_mood"] not in COVER_MOODS:
        post["cover_mood"] = "graphic"
    if roundup:
        tool_slides = [s for s in mids if s["type"] == "text"]
        names = {t.lower(): t for t in TOOLS}
        unknown = [s["kicker"] for s in tool_slides if s["kicker"].lower() not in names]
        if len(tool_slides) < 3 or unknown:
            raise InvalidPost(
                "a tool roundup needs 3 to 5 text slides whose kicker is exactly one tool name from the "
                f"allowed list (unknown: {unknown})"
            )
        for s in tool_slides:
            s["kicker"] = names[s["kicker"].lower()]
        if re.search(r"\$\d|\bfree\b|\bpric", " ".join(s["title"] + " " + s["body"] for s in mids), re.I):
            raise InvalidPost("do not mention prices or whether a tool is free")

    checked = [post["cover_title"], post["cover_subtitle"], post["caption"]]
    checked += [s[k] for s in post["slides"] for k in ("kicker", "title", "body")]
    for text in checked:
        tell = find_tell(text)
        if tell:
            raise InvalidPost(f"it contains {tell}. Rewrite that part as one plain true statement")

    all_text = json.dumps(post)
    if BANNED.search(all_text):
        raise InvalidPost("mentions AI identity")
    post["hashtags"] = [("#" + h.lstrip("#")).lower().replace(" ", "") for h in post["hashtags"]][:5]
    return post


def roundup_brief(persona: str) -> str:
    tools = "\n".join(f"- {name}: {what}" for name, what in TOOLS.items())
    return (
        f"Today is a TOOL ROUNDUP: \"AI tools worth trying if you're one of the {persona}\".\n"
        "Structure: cover (cover_mood 'graphic' works best), then 3 to 5 text slides, one per tool, then ONE "
        "prompt slide with a copy-paste prompt this person can use in ChatGPT, Claude or Gemini today, then the cta.\n"
        "On each tool slide: kicker = the exact tool name from the list below, title = what it helps this person "
        "do (max 60 characters), body = one specific, everyday way they would use it (max 200 characters).\n"
        "Only use tools from this list, and only for what the list says they do. Never mention prices, plans or "
        "whether something is free, never invent features, and never claim Tessa tested or uses a tool. "
        "In the caption, add a line saying to check each tool's current pricing and privacy settings.\n"
        f"Allowed tools:\n{tools}"
    )


def generate(pillar: str, recent_topics: list[str], date_label: str, persona: str | None = None) -> dict:
    client = anthropic.Anthropic()
    recent = "\n".join(f"- {t}" for t in recent_topics[-60:]) or "- (none yet)"
    user = (
        f"Write the carousel for {date_label}.\n"
        f"Today's content pillar: {pillar}\n\n"
        + (roundup_brief(persona) + "\n\n" if persona else "")
        + f"Recently posted (do not repeat):\n{recent}"
    )
    covers = "\n".join(f"   - {m}: {COVERS[m]}" for m in COVER_MOODS)
    system = SYSTEM.format(covers=covers)
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
            system=system,
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
            return validate(json.loads(text), roundup=persona is not None)
        except (InvalidPost, json.JSONDecodeError) as e:
            last_err = str(e)
    raise InvalidPost(f"gave up after 3 attempts: {last_err}")
