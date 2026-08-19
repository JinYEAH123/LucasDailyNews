#!/usr/bin/env python3
"""Generate one edition of Daily News for Kids into data/editions/<date>.json.

Three stories a day, from five beats, centred on the US and China. None of that
is configurable — it is the editorial line. What is generated three times is the
writing: every story is rewritten for ages 6-11, 12-15 and 16+.

The run is deliberately split into small passes:

  1. Research   — the web_search tool reads what the world published in the
                  window and produces a brief.
  2. Skeleton   — the three chosen stories, with their beats, regions and links.
                  Emitted once, so the URLs cannot drift between age bands and
                  the model is never asked to reproduce an address from memory.
  3. Per band   — the reader-facing writing for one band at a time. Three small
                  calls beat one enormous one: each is far from the token
                  ceiling, and a failure costs one band rather than the day.

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
from datetime import datetime
from pathlib import Path

import anthropic

import appconfig

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"

MODEL = "claude-opus-5"
N = appconfig.STORIES_PER_DAY


# --------------------------------------------------------------------------- schemas

def _pair(langs: list, desc: str) -> dict:
    return {
        "type": "object", "description": desc,
        "properties": {l: {"type": "string"} for l in langs},
        "required": list(langs), "additionalProperties": False,
    }


def _pair_list(langs: list, desc: str) -> dict:
    return {
        "type": "object", "description": desc,
        "properties": {l: {"type": "array", "items": {"type": "string"}} for l in langs},
        "required": list(langs), "additionalProperties": False,
    }


def skeleton_schema(cfg) -> dict:
    """Pass 2: the facts and links, emitted once for all three bands."""
    langs = cfg.languages
    reading_item = {
        "type": "object",
        "properties": {
            "title": _pair(langs, "Headline of the linked article."),
            "summary": _pair(langs, "Two sentences on what this adds and why to click."),
            "publisher": {"type": "string"},
            "url": {"type": "string", "description": "Real URL from search results."},
        },
        "required": ["title", "summary", "publisher", "url"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array", "minItems": N, "maxItems": N,
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer", "description": "1 is most important."},
                        "slug": {"type": "string",
                                 "description": "A few words identifying this story, "
                                                "used to match the writing to it."},
                        "category": {"type": "string", "enum": list(appconfig.CATEGORIES)},
                        "region": {"type": "string", "enum": list(appconfig.REGIONS)},
                        "facts": {"type": "string",
                                  "description": "The story in 4-6 plain sentences for an "
                                                 "adult: what happened, the numbers, the "
                                                 "names, and what is disputed. This is the "
                                                 "source material each band is written from."},
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
                        "background": {"type": "array", "minItems": 1, "maxItems": 3,
                                       "items": reading_item},
                        "further": {"type": "array", "minItems": 1, "maxItems": 3,
                                    "items": reading_item},
                        "videos": {
                            "type": "array", "maxItems": 2,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "channel": {"type": "string"},
                                    "url": {"type": "string"},
                                    "summary": _pair(langs, "One sentence on what it shows."),
                                },
                                "required": ["title", "channel", "url", "summary"],
                                "additionalProperties": False,
                            },
                            "description": "Leave empty rather than guessing a URL.",
                        },
                    },
                    "required": ["rank", "slug", "category", "region", "facts",
                                 "source", "background", "further", "videos"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["stories"],
        "additionalProperties": False,
    }


def band_schema(cfg, band_key: str) -> dict:
    """Pass 3: the reader-facing writing for one age band."""
    langs = cfg.languages
    band = appconfig.AGE_BANDS[band_key]
    return {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array", "minItems": N, "maxItems": N,
                "description": "In the same order as the skeleton.",
                "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "description": "Matching the skeleton."},
                        "headline": _pair(langs, "A headline that makes them want to read."),
                        "hook": _pair(langs, "2-4 sentences: what happened, plainly."),
                        "story": _pair_list(
                            langs, f"{band['paragraphs']}. {band['sentences']}"),
                        "why_it_matters": _pair(
                            langs, "2-3 sentences connecting it to this reader's own life."),
                        "word_bank": {
                            "type": "array",
                            "minItems": max(1, band["words"] - 1),
                            "maxItems": band["words"] + 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "term": _pair(langs, "The term as the news uses it."),
                                    "def": _pair(langs, "One clear sentence at this level."),
                                },
                                "required": ["term", "def"],
                                "additionalProperties": False,
                            },
                        },
                        "talk_about_it": {
                            "type": "array", "minItems": 3, "maxItems": 3,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": _pair(
                                        langs, "An open question answerable either way."),
                                    "sides": {
                                        "type": "array", "minItems": 2, "maxItems": 2,
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": _pair(langs, "Short name for this position."),
                                                "points": _pair_list(
                                                    langs, "Its 3 strongest arguments, "
                                                           "one sentence each."),
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
                    },
                    "required": ["slug", "headline", "hook", "story", "why_it_matters",
                                 "word_bank", "talk_about_it"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["stories"],
        "additionalProperties": False,
    }


# ------------------------------------------------------------------ api dialect

# Structured outputs accept a subset of JSON Schema, not all of it. The schemas
# above are written with the bounds an edition actually wants, because that is
# what they are for — saying what the output should look like. This translates
# one into what the endpoint will take on the way out, so the two can never
# drift apart in an edit, and the counts the API cannot enforce are stated in
# the prompts instead.
#
# Per platform.claude.com/docs/en/build-with-claude/structured-outputs:
# maxItems is rejected outright, and minItems accepts only 0 or 1. Numeric
# bounds, string bounds, `pattern` and `oneOf` are rejected too — they are not
# used here, and the guard below makes sure that stays true.
_API_SUPPORTED = {
    "type", "properties", "items", "required", "additionalProperties",
    "description", "enum", "const", "anyOf", "allOf", "$ref", "$defs",
    "definitions", "default", "format", "title", "minItems",
}
_API_DROPS = {"maxItems"}

_SUBSCHEMA_MAPS = ("properties", "$defs", "definitions")


def api_schema(node):
    """An authored schema, reduced to what the structured-output API accepts.

    Anything neither supported nor known-droppable raises here rather than
    coming back as a 400 — which matters because the research pass runs first
    and has already cost real money by the time a request would be rejected.
    """
    if isinstance(node, list):
        return [api_schema(v) for v in node]
    if not isinstance(node, dict):
        return node

    out = {}
    for key, value in node.items():
        if key in _SUBSCHEMA_MAPS:
            # These keys hold *names*, not keywords — a property could legally
            # be called "maxItems" — so recurse into the values only.
            out[key] = {name: api_schema(sub) for name, sub in value.items()}
        elif key in _API_DROPS:
            continue
        elif key == "minItems":
            out[key] = 1 if value else 0
        elif key in _API_SUPPORTED:
            out[key] = api_schema(value)
        else:
            raise SystemExit(
                f"Schema keyword {key!r} is not accepted by structured outputs. "
                f"Drop it, or add it to _API_SUPPORTED/_API_DROPS if the docs "
                f"say otherwise: "
                f"platform.claude.com/docs/en/build-with-claude/structured-outputs"
            )
    return out


# --------------------------------------------------------------------------- prompts

def base_policy(cfg) -> str:
    beats = ", ".join(f"{appconfig.category_label(k, 'en')}" for k in appconfig.CATEGORIES)
    langs = " and ".join(appconfig.LANGUAGES[l] for l in cfg.languages)
    return f"""\
You edit a daily news page for children, read with their parents. It is written
in {langs}.

SELECTION — exactly {N} stories from the window, ranked by importance:
- Beats: {beats}. Nothing else.
- Centre of gravity: the United States and China. Anywhere else only when the
  event is big enough to lead world coverage anywhere — a major war development,
  a Nobel Prize, a large disaster, a papal election. Tag those GLOBAL.
- Prefer {N} different beats when the importance ranking allows it, but never
  fill a slot with a weak story to reach a beat.
- Importance means consequence, not drama: how many people it affects, how long
  the effects last, whether something structural changed. Celebrity gossip is not
  a top story. Crime and gore are not top stories.
- Never pick several stories that are really the same story.

Every URL you output must be one you saw in a search result during research.
Never construct, guess, or repair a URL. An empty list beats an invented link.\
"""


def writing_policy(cfg, band_key: str) -> str:
    band = appconfig.AGE_BANDS[band_key]
    return base_policy(cfg) + f"""

WRITING — this pass is for readers aged {band_key}:
- {band['voice']}
- {band['sentences']}
- Lead with the concrete thing that happened, never with abstraction.
- Explain every piece of jargon the first time. Use comparisons the reader can
  picture, drawn from their own life rather than from abstract scale.
- Respect them. Do not moralise, do not talk down, do not add fake excitement.
  Real stakes are more interesting than exclamation marks.
- Where adults disagree about what a fact means, say so and give both readings.
- Keep every language natural in its own right — a fluent rewrite, never a
  word-by-word translation.
- The same three stories are being written for two other age bands. Do not
  soften which story is being told; change only how it is explained.

THE THINKING EXERCISE — exactly three dinner-table questions per story, each
with exactly two sides. Treat it as the hardest thing you write:
- A question qualifies only if a thoughtful, well-informed adult could genuinely
  land on either side. If looking something up settles it, it is a quiz question.
- {band['questions']}
- Argue both sides at full strength — each gets its best three arguments, never
  two good ones and a weak one set up to be knocked down.
- Never signal which side you favour: not in the order, not in the labels, not
  by giving one side more or better-written points.
- Where a side's strongest argument is uncomfortable, make it anyway."""


def research_prompt(cfg, start, end, date_str: str) -> str:
    beats = ", ".join(appconfig.category_label(k, "en") for k in appconfig.CATEGORIES)
    return f"""\
Today is {date_str}. Research the news for the edition covering:

  {start:%A %B %d, %Y at %-I:%M %p} to {end:%A %B %d, %Y at %-I:%M %p} ({cfg.timezone})

Search widely across major outlets — wire services, national papers, specialist
press — for what was actually published in that window. Beats: {beats}. Centre of
gravity: the United States and China.

Write a research brief containing:

1. A ranked shortlist of about {N * 2 + 2} candidates. For each: what happened,
   the specific numbers and names, why it matters, its beat, its region.
2. Your top {N}, a sentence on each choice, and a sentence on what you left out.
3. For each pick: the main source URL, 2-3 background/further reading URLs from
   different outlets, and any real YouTube explainer you found.

Paste URLs exactly as they appeared in search results. Note anything disputed or
unconfirmed — that matters more than completeness."""


def skeleton_prompt(brief: str) -> str:
    return f"""\
<brief>
{brief}
</brief>

Emit the {N} chosen stories as JSON: rank, a short slug, beat, region, the links,
and a plain adult-level `facts` paragraph for each. The facts field is the source
material three separate age-band rewrites will each work from, so it must contain
every number, name and disputed point they might need.

Use only URLs that appear in the brief."""


def band_prompt(skeleton: dict, band_key: str) -> str:
    band = appconfig.AGE_BANDS[band_key]
    listing = "\n\n".join(
        f"{s['rank']}. slug: {s['slug']}  [{s['category']} · {s['region']}]\n{s['facts']}"
        for s in skeleton["stories"]
    )
    return f"""\
Write these {N} stories for readers aged {band_key}. Keep the same order and
reuse each slug exactly. About {band['words']} words per story in the word bank.

{listing}

Do not add links — those are already recorded. Write only the reader-facing text."""


# --------------------------------------------------------------------------- api

def _text_of(message) -> str:
    return "\n".join(b.text for b in message.content if b.type == "text").strip()


def _guard(message, what: str):
    if message.stop_reason == "refusal":
        detail = getattr(message.stop_details, "explanation", "") or ""
        raise SystemExit(f"{what} was declined: {detail}")
    return message


def research(client, cfg, prompt: str, max_restarts: int = 4) -> str:
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 20}]

    for attempt in range(max_restarts + 1):
        with client.messages.stream(
            model=MODEL, max_tokens=32000, system=base_policy(cfg),
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            tools=tools, messages=messages,
        ) as stream:
            message = _guard(stream.get_final_message(), "Research")

        if message.stop_reason != "pause_turn":
            brief = _text_of(message)
            if not brief:
                raise SystemExit("Research produced no text.")
            return brief

        messages.append({"role": "assistant", "content": message.content})
        print(f"  research paused, resuming ({attempt + 1}/{max_restarts})", file=sys.stderr)

    raise SystemExit("Research never finished — still paused after max restarts.")


def structured(client, cfg, system: str, prompt: str, schema: dict, what: str) -> dict:
    with client.messages.stream(
        model=MODEL, max_tokens=32000, system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema",
                                  "schema": api_schema(schema)}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = _guard(stream.get_final_message(), what)
    return json.loads(_text_of(message))


# --------------------------------------------------------------------------- assembly

PER_BAND = ["headline", "hook", "story", "why_it_matters", "word_bank", "talk_about_it"]


def build_edition(cfg, skeleton: dict, bands: dict, date_str: str, start, end) -> dict:
    stories = sorted(skeleton["stories"], key=lambda s: s.get("rank", 99))

    for i, story in enumerate(stories, 1):
        story["rank"] = i
        story["versions"] = {}
        for band_key, payload in bands.items():
            by_slug = {s["slug"]: s for s in payload["stories"]}
            written = by_slug.get(story["slug"])
            if written is None:
                # Matching by slug failed; fall back to position so a band is
                # never silently dropped from the page.
                ordered = payload["stories"]
                written = ordered[i - 1] if i - 1 < len(ordered) else None
                print(f"  note: band {band_key} slug mismatch for "
                      f"{story['slug']!r}, matched by position", file=sys.stderr)
            if written:
                story["versions"][band_key] = {k: written[k] for k in PER_BAND}
        story["versions"] = {k: story["versions"][k]
                             for k in appconfig.AGE_BANDS if k in story["versions"]}
        story.pop("slug", None)
        story.pop("facts", None)

    label = {}
    zone = appconfig.tz_abbrev(cfg, end)
    if "en" in cfg.languages:
        label["en"] = (f"News from {start:%A} {start:%-I:%M %p} to "
                       f"{end:%A} {end:%-I:%M %p} {zone}")
    if "zh" in cfg.languages:
        label["zh"] = f"{zone} {start:%-m月%-d日} {start:%H:%M} 至 {end:%-m月%-d日} {end:%H:%M}"

    return {
        "date": date_str,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "label": label},
        "generated_at": datetime.now(cfg.tz).isoformat(timespec="seconds"),
        "generator": f"{MODEL} (research + skeleton + {len(bands)} bands)",
        "settings": {
            "stories_per_day": N,
            "categories": list(appconfig.CATEGORIES),
            "regions": list(appconfig.REGIONS),
            "bands": list(appconfig.AGE_BANDS),
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
    date_str, start, end = appconfig.resolve_window(cfg, args.date)
    out_path = EDITIONS_DIR / f"{date_str}.json"

    if out_path.exists() and not args.force and not args.dry_run:
        print(f"{out_path.relative_to(ROOT)} already exists. Use --force to regenerate.")
        return

    print(f"Edition {date_str}: {start:%b %d %-I:%M %p} → {end:%b %d %-I:%M %p} ({cfg.timezone})")
    print(f"  {N} stories · bands {'/'.join(appconfig.AGE_BANDS)} · {'/'.join(cfg.languages)}")

    # Translate every schema up front. Pass 2 is the first that sends one, by
    # which point the research pass has already been paid for — so an
    # unsendable schema should stop the run here, not three minutes in.
    api_schema(skeleton_schema(cfg))
    for band_key in appconfig.AGE_BANDS:
        api_schema(band_schema(cfg, band_key))

    client = anthropic.Anthropic()

    print("Pass 1 — researching…")
    brief = research(client, cfg, research_prompt(cfg, start, end, date_str))
    print(f"  brief: {len(brief)} characters")

    print("Pass 2 — choosing and recording the links…")
    skeleton = structured(client, cfg, base_policy(cfg), skeleton_prompt(brief),
                          skeleton_schema(cfg), "Skeleton")
    for s in sorted(skeleton["stories"], key=lambda s: s["rank"]):
        print(f"  {s['rank']}. [{s['category']}·{s['region']}] {s['slug']}")

    bands = {}
    for i, band_key in enumerate(appconfig.AGE_BANDS, 1):
        print(f"Pass 3.{i} — writing for {band_key}…")
        bands[band_key] = structured(
            client, cfg, writing_policy(cfg, band_key), band_prompt(skeleton, band_key),
            band_schema(cfg, band_key), f"Band {band_key}")

    edition = build_edition(cfg, skeleton, bands, date_str, start, end)
    text = json.dumps(edition, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        print(text)
        return

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    lang = cfg.primary_language
    for story in edition["stories"]:
        head = story["versions"].get(cfg.band, {}).get("headline", {}).get(lang, "")
        print(f"  {story['rank']}. [{story['category']}] {head}")


if __name__ == "__main__":
    main()
