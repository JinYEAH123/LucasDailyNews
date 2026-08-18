#!/usr/bin/env python3
"""Generate one edition of Daily News for Kids into data/editions/<date>.json.

Everything editorial — how many stories, which beats, which parts of the world,
how the writing is pitched — comes from config.toml, so the same code serves a
7-year-old who wants sports and space and a 16-year-old who wants markets.

Two passes against the Claude API:

  1. Research  — Claude uses the server-side web_search tool to read what the
                 world's outlets published inside the edition window.
  2. Rewrite   — the brief becomes strict JSON matching a schema built from the
                 family's settings, rewritten for a child of the configured age.

Splitting the passes keeps the searching turn free to run long (and to be
resumed after `pause_turn`) while the JSON turn stays deterministic.

Usage:
    python3 scripts/generate_edition.py                 # current window
    python3 scripts/generate_edition.py --date 2026-08-16
    python3 scripts/generate_edition.py --force         # overwrite
    python3 scripts/generate_edition.py --dry-run       # print, don't write

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile) and `pip install anthropic`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

import anthropic

import appconfig

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"

MODEL = "claude-opus-5"


# --------------------------------------------------------------------------- schema

def build_schema(cfg: appconfig.Config) -> dict:
    """Build the output schema from the family's settings.

    Only the configured languages are required, so a single-language family is
    not billed for a translation nobody reads.
    """
    langs = cfg.languages

    def pair(desc: str) -> dict:
        return {
            "type": "object",
            "description": desc,
            "properties": {l: {"type": "string"} for l in langs},
            "required": list(langs),
            "additionalProperties": False,
        }

    def pair_list(desc: str) -> dict:
        return {
            "type": "object",
            "description": desc,
            "properties": {
                l: {"type": "array", "items": {"type": "string"}} for l in langs
            },
            "required": list(langs),
            "additionalProperties": False,
        }

    reading_item = {
        "type": "object",
        "properties": {
            "title": pair("Headline of the linked article."),
            "summary": pair("Two sentences on what this adds and why they might click."),
            "publisher": {"type": "string"},
            "url": {"type": "string", "description": "Real URL from search results."},
        },
        "required": ["title", "summary", "publisher", "url"],
        "additionalProperties": False,
    }

    profile = cfg.profile

    return {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array",
                "minItems": cfg.count,
                "maxItems": cfg.count,
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer", "description": "1 is most important."},
                        "category": {"type": "string", "enum": list(cfg.categories)},
                        "region": {
                            "type": "string",
                            "enum": list(cfg.regions) + ["GLOBAL"],
                        },
                        "headline": pair("A headline that makes them want to click."),
                        "hook": pair("2-4 sentences: what happened, plainly. The teaser."),
                        "story": pair_list(
                            f"{profile['paragraphs']} rewriting the adult reporting. "
                            f"{profile['sentences']}"
                        ),
                        "why_it_matters": pair(
                            "2-3 sentences connecting the story to this child's own life."
                        ),
                        "talk_about_it": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "description": "The thinking exercise. See EDITORIAL_POLICY.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": pair(
                                        "An open question answerable either way. "
                                        "Never a fact lookup."
                                    ),
                                    "sides": {
                                        "type": "array",
                                        "minItems": 2,
                                        "maxItems": 2,
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": pair("Short name for this position."),
                                                "points": pair_list(
                                                    "The 3 strongest arguments for it, "
                                                    "one sentence each."
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
                            "minItems": max(1, profile["words"] - 1),
                            "maxItems": profile["words"] + 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "term": pair("The term as it appears in the news."),
                                    "def": pair("One clear sentence at this reading level."),
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
                            "type": "array", "minItems": 1, "maxItems": 3,
                            "items": reading_item,
                            "description": "Explainers for someone new to the backstory.",
                        },
                        "further": {
                            "type": "array", "minItems": 1, "maxItems": 3,
                            "items": reading_item,
                            "description": "Where to go once the basics are clear.",
                        },
                        "videos": {
                            "type": "array", "maxItems": 2,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "channel": {"type": "string"},
                                    "url": {"type": "string"},
                                    "summary": pair("One sentence on what it shows."),
                                },
                                "required": ["title", "channel", "url", "summary"],
                                "additionalProperties": False,
                            },
                            "description": "Leave empty rather than guessing a URL.",
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

def editorial_policy(cfg: appconfig.Config) -> str:
    p = cfg.profile
    beats = ", ".join(
        f"{k} ({cfg.label('category', k, 'en')})" for k in cfg.categories
    )
    places = ", ".join(cfg.label("region", r, "en") for r in cfg.regions)
    who = f"a {cfg.age}-year-old" + (f" named {cfg.child_name}" if cfg.child_name else "")
    langs = " and ".join(appconfig.LANGUAGES[l] for l in cfg.languages)
    spread = min(len(cfg.categories), cfg.count)

    return f"""\
You edit a daily news page read by {who} and their parents, usually together.
It is written in {langs}.

SELECTION — pick exactly {cfg.count} stories from the window, ranked by importance:
- Draw them only from these beats: {beats}.
- Focus on these parts of the world: {places}. Cover somewhere else only when
  the event is big enough to lead world coverage anywhere — a major war
  development, a Nobel Prize, a large disaster, a papal election.
- Spread the {cfg.count} across at least {spread} different beats when the
  importance ranking allows it. Never fill a slot with a weak story just to
  reach a beat; a genuinely important story outranks variety.
- Importance means consequence, not drama: how many people it affects, how long
  the effects last, whether it changes something structural. Celebrity gossip is
  not a top story. Crime and gore are not top stories.
- Do not pick several stories that are really the same story.

WRITING — for a reader of {cfg.age}:
- {p['voice']}
- {p['sentences']}
- Lead with the concrete thing that happened, never with abstraction.
- Explain every piece of jargon the first time. Use comparisons they can
  picture, and prefer ones from their own life over abstract scale.
- Respect them. Do not moralise, do not talk down, do not add fake excitement.
  Real stakes are more interesting than exclamation marks.
- Where adults disagree about what a fact means, say so and give both readings.
  Never present a contested claim as settled.
- Keep every language natural in its own right — a fluent rewrite, never a
  word-by-word translation of the English.

THE THINKING EXERCISE — three dinner-table questions per story, each with the
case for both sides. This is the part of the page that matters most, so treat it
as the hardest thing you write:
- A question qualifies only if a thoughtful, well-informed adult could genuinely
  land on either side. If looking something up settles it, it is a quiz question
  and belongs nowhere on this page.
- {p['questions']}
- Argue both sides at full strength. Give each its best three arguments, not two
  good ones and a weak one you plan to knock down. If one side comes out flimsy,
  either the question is bad or you are not arguing it honestly — fix the
  question rather than shading the answer.
- Never signal which side you favour: not in the order, not in the labels, not
  by giving one side more or better-written points.
- Where a side's strongest argument is uncomfortable, make it anyway. A
  sanitised case is a dishonest one.

LINKS — background reading (start here if you're new to this) and further
reading (go deeper), each a title plus a short summary so they can decide before
clicking. Prefer outlets with different viewpoints. Add a YouTube video only if
the search results actually surfaced a real one.

Every URL you output must be one you saw in a search result during research.
Never construct, guess, or repair a URL. An empty list beats an invented link.\
"""


def research_prompt(cfg: appconfig.Config, start: datetime, end: datetime, date_str: str) -> str:
    beats = ", ".join(cfg.label("category", k, "en") for k in cfg.categories)
    places = ", ".join(cfg.label("region", r, "en") for r in cfg.regions)
    shortlist = cfg.count * 2 + 2

    return f"""\
Today is {date_str}. Research the news for the edition covering:

  {start:%A %B %d, %Y at %-I:%M %p} to {end:%A %B %d, %Y at %-I:%M %p} ({cfg.timezone})

Search widely across major outlets — wire services, national papers, and
specialist press — for what was actually published in that window.
Cover these beats: {beats}.
Centre of gravity: {places}.

Then write a research brief containing:

1. A ranked shortlist of about {shortlist} candidate stories. For each: what
   happened, the specific numbers and names, why it might matter, its beat, and
   its region.
2. Your pick of the top {cfg.count}, a sentence explaining each choice, and a
   sentence on what you left out and why.
3. For each pick: the main source URL, 2-3 candidate background/further reading
   URLs from different outlets, and any real YouTube explainer you found.

Paste URLs exactly as they appeared in search results. Note anything disputed or
still unconfirmed — that matters more than completeness."""


def rewrite_prompt(cfg: appconfig.Config, brief: str, start: datetime, end: datetime) -> str:
    return f"""\
Here is today's research brief for the window {start:%b %d %-I:%M %p} –
{end:%b %d %-I:%M %p} ({cfg.timezone}).

<brief>
{brief}
</brief>

Turn the top {cfg.count} into the edition JSON. Rank 1 is the most important.
Use only URLs that appear in the brief."""


# --------------------------------------------------------------------------- window

def resolve_window(cfg: appconfig.Config, date_str: str | None,
                   now: datetime | None = None) -> tuple:
    """Return (edition_date, window_start, window_end) in the family's zone.

    The edition dated D covers D-1 at the cutoff hour through D at the cutoff
    hour. Before the cutoff, the newest complete edition is still yesterday's.
    """
    tz = cfg.tz
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now = now or datetime.now(tz)
        day = now.date() if now.hour >= cfg.hour else (now - timedelta(days=1)).date()

    end = datetime.combine(day, dtime(cfg.hour, 0), tzinfo=tz)
    return day.isoformat(), end - timedelta(days=1), end


# --------------------------------------------------------------------------- api

def _text_of(message) -> str:
    return "\n".join(b.text for b in message.content if b.type == "text").strip()


def research(client, cfg, prompt: str, max_restarts: int = 4) -> str:
    """Pass 1 — search the web and return the brief. Resumes across pause_turn."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search",
              "max_uses": min(40, 10 + cfg.count * 4)}]

    for attempt in range(max_restarts + 1):
        with client.messages.stream(
            model=MODEL,
            max_tokens=32000,
            system=editorial_policy(cfg),
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

        messages.append({"role": "assistant", "content": message.content})
        print(f"  research paused, resuming ({attempt + 1}/{max_restarts})", file=sys.stderr)

    raise SystemExit("Research turn never finished — still paused after max restarts.")


def rewrite(client, cfg, prompt: str) -> dict:
    """Pass 2 — turn the brief into schema-valid JSON. No tools, so no pause_turn."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=editorial_policy(cfg),
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": build_schema(cfg)},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        detail = getattr(message.stop_details, "explanation", "") or ""
        raise SystemExit(f"Rewrite turn was declined: {detail}")

    return json.loads(_text_of(message))


# --------------------------------------------------------------------------- main

def window_label(cfg: appconfig.Config, start: datetime, end: datetime) -> dict:
    labels = {}
    if "en" in cfg.languages:
        labels["en"] = (f"News from {start:%A} {start:%-I:%M %p} to "
                        f"{end:%A} {end:%-I:%M %p}, {cfg.timezone.split('/')[-1].replace('_', ' ')} time")
    if "zh" in cfg.languages:
        labels["zh"] = f"当地时间 {start:%-m月%-d日} {start:%H:%M} 至 {end:%-m月%-d日} {end:%H:%M}"
    return labels


def build_edition(cfg, payload: dict, date_str: str, start: datetime, end: datetime) -> dict:
    stories = sorted(payload["stories"], key=lambda s: s.get("rank", 99))
    for i, story in enumerate(stories, 1):
        story["rank"] = i
    return {
        "date": date_str,
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": window_label(cfg, start, end),
        },
        "generated_at": datetime.now(cfg.tz).isoformat(timespec="seconds"),
        "generator": f"{MODEL} (web search + rewrite)",
        # Recorded so an old edition still renders after the settings change.
        "settings": {
            "age": cfg.age,
            "count": cfg.count,
            "categories": cfg.categories,
            "regions": cfg.regions,
            "languages": cfg.languages,
            "timezone": cfg.timezone,
            "hour": cfg.hour,
        },
        "stories": stories,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate one edition.")
    ap.add_argument("--date", help="Edition date, YYYY-MM-DD. Defaults to the current window.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing edition file.")
    ap.add_argument("--dry-run", action="store_true", help="Print the JSON instead of writing.")
    args = ap.parse_args()

    cfg = appconfig.load()
    date_str, start, end = resolve_window(cfg, args.date)
    out_path = EDITIONS_DIR / f"{date_str}.json"

    if out_path.exists() and not args.force and not args.dry_run:
        print(f"{out_path.relative_to(ROOT)} already exists. Use --force to regenerate.")
        return

    print(f"Edition {date_str}: {start:%b %d %-I:%M %p} → {end:%b %d %-I:%M %p} ({cfg.timezone})")
    print(f"  {cfg.count} stories · age {cfg.age} · {'/'.join(cfg.categories)} "
          f"· {'/'.join(cfg.regions)}")

    client = anthropic.Anthropic()

    print("Pass 1/2 — researching…")
    brief = research(client, cfg, research_prompt(cfg, start, end, date_str))
    print(f"  brief: {len(brief)} characters")

    print("Pass 2/2 — rewriting…")
    payload = rewrite(client, cfg, rewrite_prompt(cfg, brief, start, end))

    edition = build_edition(cfg, payload, date_str, start, end)
    text = json.dumps(edition, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        print(text)
        return

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    lang = cfg.primary_language
    for story in edition["stories"]:
        print(f"  {story['rank']}. [{story['category']}] {story['headline'][lang]}")


if __name__ == "__main__":
    main()
