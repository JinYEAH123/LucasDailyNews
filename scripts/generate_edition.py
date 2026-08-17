#!/usr/bin/env python3
"""Generate one edition of Lucas Daily News and write it to data/editions/<date>.json.

Two passes against the Claude API:

  1. Research  — Claude uses the server-side web_search tool to read what global
                 outlets published inside the edition window, then writes a brief.
  2. Rewrite   — the brief is turned into strict JSON matching EDITION_SCHEMA,
                 rewritten for a 12-year-old reader, in English and Chinese.

Splitting the passes keeps the searching turn free to run long (and to be
resumed after `pause_turn`) while the JSON turn stays deterministic.

Usage:
    python3 scripts/generate_edition.py                 # edition for the current window
    python3 scripts/generate_edition.py --date 2026-08-16
    python3 scripts/generate_edition.py --force         # overwrite an existing file
    python3 scripts/generate_edition.py --dry-run       # print, don't write

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile) and `pip install anthropic`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"

VANCOUVER = ZoneInfo("America/Vancouver")
CUTOFF_HOUR = 17  # 5:00 PM, dinner time

MODEL = "claude-opus-5"

# --------------------------------------------------------------------------- schema

def _pair(desc: str) -> dict:
    return {
        "type": "object",
        "description": desc,
        "properties": {
            "en": {"type": "string"},
            "zh": {"type": "string"},
        },
        "required": ["en", "zh"],
        "additionalProperties": False,
    }


def _pair_list(desc: str) -> dict:
    return {
        "type": "object",
        "description": desc,
        "properties": {
            "en": {"type": "array", "items": {"type": "string"}},
            "zh": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["en", "zh"],
        "additionalProperties": False,
    }


READING_ITEM = {
    "type": "object",
    "properties": {
        "title": _pair("Headline of the linked article."),
        "summary": _pair("Two sentences on what this article adds and why Lucas might click it."),
        "publisher": {"type": "string"},
        "url": {"type": "string", "description": "Real URL seen in search results. Never invented."},
    },
    "required": ["title", "summary", "publisher", "url"],
    "additionalProperties": False,
}

EDITION_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer", "description": "1 is the most important."},
                    "category": {"type": "string", "enum": ["politics", "society", "business", "tech"]},
                    "region": {"type": "string", "enum": ["US", "CN", "GLOBAL"]},
                    "headline": _pair("Punchy headline a 12-year-old wants to click. Not a label."),
                    "hook": _pair("2-4 sentences: what happened, in plain language. The teaser."),
                    "story": _pair_list(
                        "4-6 short paragraphs rewriting the adult reporting for a curious "
                        "12-year-old: concrete comparisons, no jargon left unexplained."
                    ),
                    "why_it_matters": _pair("2-3 sentences connecting the story to Lucas's own life."),
                    "talk_about_it": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "description": "The independent-thinking exercise. See EDITORIAL_POLICY.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": _pair(
                                    "An open question a thoughtful adult could answer either way. "
                                    "Never a fact lookup, never a question with a correct answer."
                                ),
                                "sides": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 2,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": _pair(
                                                "Short name for this position, e.g. "
                                                "'Yes — it did real work'."
                                            ),
                                            "points": _pair_list(
                                                "The 3 strongest arguments for this position, "
                                                "each one sentence."
                                            ),
                                        },
                                        "required": ["label", "points"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["question", "sides"],
                            "additionalProperties": False,
                        },
                    },
                    "word_bank": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "term": _pair("The term as it appears in the news."),
                                "def": _pair("One clear sentence a 12-year-old understands."),
                            },
                            "required": ["term", "def"],
                            "additionalProperties": False,
                        },
                    },
                    "source": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "publisher": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["title", "publisher", "url"],
                        "additionalProperties": False,
                    },
                    "background": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": READING_ITEM,
                        "description": "Explainers for a reader who does not know the backstory yet.",
                    },
                    "further": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": READING_ITEM,
                        "description": "Where to go next once the basics are clear.",
                    },
                    "videos": {
                        "type": "array",
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "channel": {"type": "string"},
                                "url": {"type": "string", "description": "Real YouTube URL from search results."},
                                "summary": _pair("One sentence on what the video shows."),
                            },
                            "required": ["title", "channel", "url", "summary"],
                            "additionalProperties": False,
                        },
                        "description": "Leave empty rather than guessing a video URL.",
                    },
                },
                "required": [
                    "rank", "category", "region", "headline", "hook", "story",
                    "why_it_matters", "talk_about_it", "word_bank", "source",
                    "background", "further", "videos",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stories"],
    "additionalProperties": False,
}

# --------------------------------------------------------------------------- prompts

EDITORIAL_POLICY = """\
You edit a daily news page for Lucas, a 12-year-old boy in Grade 7 who lives in
Vancouver and reads it with his parents over dinner. His parents read Chinese.

SELECTION — pick exactly 3 stories from the window, ranked by importance:
- Draw them from four beats: politics, society, business/finance, and technology.
  Three stories cannot cover four beats; pick the three that genuinely mattered
  most, and prefer a spread of beats over three stories from one beat.
- Focus on China and the United States. Cover another country or another beat
  only when the event is big enough to lead world coverage anywhere — a major
  war development, a Nobel Prize, a large disaster, a papal election.
- Importance means consequence, not drama: how many people it affects, how long
  the effects last, whether it changes something structural. A celebrity story
  is not a top-3 story. Crime and gore are not top-3 stories.
- Do not pick three stories that are really the same story.

WRITING — rewrite adult reporting so a bright 12-year-old wants to keep reading:
- Lead with the concrete thing that happened, never with abstraction.
- Explain every piece of jargon the first time. Use comparisons he can picture,
  and prefer local ones (distances near Vancouver, prices in a store, a school
  analogy) over abstract scale.
- Respect him. Do not moralize, do not talk down, do not add fake excitement.
  Real stakes are more interesting than exclamation marks.
- Where adults disagree about what a fact means, say so and give both readings.
  Never pretend a contested claim is settled.
- Keep the Chinese natural — a fluent rewrite for a Chinese-reading parent, not
  a word-by-word translation of the English.

THE THINKING EXERCISE — three dinner-table questions per story, each with the
case for both sides. This is the part of the page that matters most, so treat it
as the hardest thing you write, not as a footer:
- A question qualifies only if a thoughtful, well-informed adult could genuinely
  land on either side. If looking something up settles it, it is not a question —
  it is a quiz, and it belongs nowhere on this page.
- Argue both sides at full strength. Give each its best three arguments, not two
  good ones and a weak one you plan to knock down. If one side comes out flimsy,
  either you picked a bad question or you are not arguing it honestly — fix the
  question rather than shading the answer.
- Never signal which side you favour: not in the order, not in the labels, not
  by giving one side more or better-written points. Lucas must not be able to
  reverse-engineer your opinion from the layout.
- Keep each point to one sentence a 12-year-old can hold in his head, and prefer
  arguments he could test against something he has actually seen.
- Where a side's strongest argument is uncomfortable, make it anyway. A sanitised
  case is a dishonest one.

LINKS — background reading (start here if you're new to this) and further
reading (go deeper), each a title plus a short summary so he can decide before
clicking. Prefer outlets with different viewpoints. Add a YouTube video only if
the search results actually surfaced a real one.

Every URL you output must be one you saw in a search result during research.
Never construct, guess, or repair a URL. An empty list beats an invented link.\
"""


def research_prompt(window_start: datetime, window_end: datetime, date_str: str) -> str:
    return f"""\
Today is {date_str}. Research the news for the edition covering:

  {window_start:%A %B %d, %Y at %-I:%M %p} to {window_end:%A %B %d, %Y at %-I:%M %p} (Vancouver time)

Search widely across major global outlets — American, Chinese, and international
wire services and papers — for what was actually published in that window.
Cover politics, society, business/finance, and technology, with China and the
United States as the centre of gravity.

Then write a research brief containing:

1. A ranked shortlist of 6-8 candidate stories. For each: what happened, the
   specific numbers and names involved, why it might matter, its beat, and its
   country.
2. Your pick of the top 3 with a sentence explaining each choice, and a sentence
   on what you left out and why.
3. For each of the top 3: the main source URL, 2-3 candidate background/further
   reading URLs from different outlets, and any real YouTube explainer you found.

Paste URLs exactly as they appeared in search results. Note anything that is
disputed or still unconfirmed — that matters more than completeness."""


def rewrite_prompt(brief: str, window_start: datetime, window_end: datetime) -> str:
    return f"""\
Here is today's research brief for the window {window_start:%b %d %-I:%M %p} –
{window_end:%b %d %-I:%M %p} Vancouver time.

<brief>
{brief}
</brief>

Turn the top 3 into the edition JSON. Rank 1 is the most important story.
Use only URLs that appear in the brief."""


# --------------------------------------------------------------------------- window

def resolve_window(date_str: str | None, now: datetime | None = None) -> tuple[str, datetime, datetime]:
    """Return (edition_date, window_start, window_end) in Vancouver time.

    The edition dated D covers D-1 5:00 PM through D 5:00 PM. Before 5:00 PM
    local, the newest *complete* edition is still yesterday's.
    """
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now = now or datetime.now(VANCOUVER)
        day = now.date() if now.hour >= CUTOFF_HOUR else (now - timedelta(days=1)).date()

    end = datetime.combine(day, dtime(CUTOFF_HOUR, 0), tzinfo=VANCOUVER)
    return day.isoformat(), end - timedelta(days=1), end


# --------------------------------------------------------------------------- api

def _text_of(message) -> str:
    return "\n".join(b.text for b in message.content if b.type == "text").strip()


def research(client: anthropic.Anthropic, prompt: str, max_restarts: int = 4) -> str:
    """Pass 1 — search the web and return the brief. Resumes across pause_turn."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 20}]

    for attempt in range(max_restarts + 1):
        with client.messages.stream(
            model=MODEL,
            max_tokens=32000,
            system=EDITORIAL_POLICY,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            detail = getattr(message.stop_details, "explanation", "") or ""
            raise SystemExit(f"Research turn was declined: {detail}")

        if message.stop_reason != "pause_turn":
            brief = _text_of(message)
            if not brief:
                raise SystemExit("Research turn produced no text.")
            return brief

        # Server tool hit its per-turn ceiling — hand the paused turn back to continue.
        messages.append({"role": "assistant", "content": message.content})
        print(f"  research paused, resuming ({attempt + 1}/{max_restarts})", file=sys.stderr)

    raise SystemExit("Research turn never finished — still paused after max restarts.")


def rewrite(client: anthropic.Anthropic, prompt: str) -> dict:
    """Pass 2 — turn the brief into schema-valid JSON. No tools, so no pause_turn."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=EDITORIAL_POLICY,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": EDITION_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        detail = getattr(message.stop_details, "explanation", "") or ""
        raise SystemExit(f"Rewrite turn was declined: {detail}")

    return json.loads(_text_of(message))


# --------------------------------------------------------------------------- main

def build_edition(payload: dict, date_str: str, start: datetime, end: datetime) -> dict:
    stories = sorted(payload["stories"], key=lambda s: s.get("rank", 99))
    for i, story in enumerate(stories, 1):
        story["rank"] = i
    return {
        "date": date_str,
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": {
                "en": f"News from {start:%A} {start:%-I:%M %p} to {end:%A} {end:%-I:%M %p}, Vancouver time",
                "zh": f"温哥华时间 {start:%-m月%-d日} 下午5点 至 {end:%-m月%-d日} 下午5点",
            },
        },
        "generated_at": datetime.now(VANCOUVER).isoformat(timespec="seconds"),
        "generator": f"{MODEL} (web search + rewrite)",
        "stories": stories,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate one Lucas Daily News edition.")
    ap.add_argument("--date", help="Edition date, YYYY-MM-DD. Defaults to the current window.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing edition file.")
    ap.add_argument("--dry-run", action="store_true", help="Print the JSON instead of writing it.")
    args = ap.parse_args()

    date_str, start, end = resolve_window(args.date)
    out_path = EDITIONS_DIR / f"{date_str}.json"

    if out_path.exists() and not args.force and not args.dry_run:
        print(f"{out_path.relative_to(ROOT)} already exists. Use --force to regenerate.")
        return

    print(f"Edition {date_str}: {start:%b %d %-I:%M %p} → {end:%b %d %-I:%M %p} Vancouver")

    client = anthropic.Anthropic()

    print("Pass 1/2 — researching…")
    brief = research(client, research_prompt(start, end, date_str))
    print(f"  brief: {len(brief)} characters")

    print("Pass 2/2 — rewriting for Lucas…")
    payload = rewrite(client, rewrite_prompt(brief, start, end))

    edition = build_edition(payload, date_str, start, end)
    text = json.dumps(edition, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        print(text)
        return

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    for story in edition["stories"]:
        print(f"  {story['rank']}. [{story['category']}] {story['headline']['en']}")


if __name__ == "__main__":
    main()
