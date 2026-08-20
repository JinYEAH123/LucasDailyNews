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
  3. Per story  — the reader-facing writing, one story and one reading level at
                  a time. Nine small calls beat three large ones: asking for
                  three stories in two languages at once was enough to make the
                  model fill in the structure and leave the prose empty, and a
                  bad answer now costs one story rather than the day.

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
import jsonschema

import appconfig

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"

MODEL = "claude-sonnet-5"
N = appconfig.STORIES_PER_DAY

# The fields one band's writing pass produces for one story.
PER_BAND = ["headline", "hook", "story", "why_it_matters", "word_bank", "talk_about_it"]


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
    """Pass 3: the reader-facing writing for **one story** at one reading level.

    One story per request rather than all three. Asking for three at once means
    three stories, in two languages, each with several paragraphs, a word bank
    and its two-sided questions, held together in a single answer — and when
    that is too much the model does not fail, it completes the structure and
    leaves the prose empty. Splitting it makes each answer small enough to write
    properly, and makes a bad one cost one story instead of the day.
    """
    langs = cfg.languages
    band = appconfig.AGE_BANDS[band_key]
    return {
        "type": "object",
        "properties": {
            "headline": _pair(langs, "A headline that makes them want to read."),
            "hook": _pair(langs, "2-4 sentences: what happened, plainly."),
            "story": _pair_list(langs, f"{band['paragraphs']}. {band['sentences']}"),
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
                "type": "array", "minItems": 2, "maxItems": 2,
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
        "required": PER_BAND,
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

SOURCES — who is allowed to be cited, and in which slot:
- The main source must be original reporting from an outlet with a newsroom and
  a corrections policy: a wire service, a national or major regional paper, a
  public broadcaster, or the specialist press of the field in question. A
  primary document — a court filing, a bill, a statistical release, a company
  statement — is always welcome in its own right.
- Never a main source: aggregators and content farms that rewrite other
  people's reporting, personal blogs and newsletters, press releases dressed as
  news, and any organisation campaigning on the subject.
- Never anywhere: a company writing about a market it sells into. An asset
  manager on the economy, a vendor on its own technology — they may be right,
  but they are not disinterested and a child cannot see the interest.
- An outlet that argues a line, or is owned or directed by a government, may be
  used for how that side sees it — but say so in the same breath, and never let
  it stand alone as the account of what happened.
- Prefer two outlets that do not share an owner over two that do. If the only
  accounts of a story trace back to one newsroom, say that in `facts`.

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

THE THINKING EXERCISE — exactly two dinner-table questions per story, each
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


def band_prompt(story: dict, band_key: str) -> str:
    band = appconfig.AGE_BANDS[band_key]
    return f"""\
Write this one story for readers aged {band_key}. About {band['words']} terms in
the word bank, and exactly two questions with two sides each.

[{story['category']} · {story['region']}]
{story['facts']}

Do not add links — those are already recorded. Write only the reader-facing text."""


# --------------------------------------------------------------------------- api

def _text_of(message) -> str:
    return "\n".join(b.text for b in message.content if b.type == "text").strip()


# Claude Sonnet 5, USD per token. Output covers thinking as well as the answer,
# which is the part worth watching: it is invisible in the finished edition and
# can be the larger half of the bill. A cache hit is a tenth of base input.
PRICE_IN, PRICE_OUT = 2 / 1e6, 10 / 1e6
PRICE_CACHE_READ, PRICE_CACHE_WRITE = PRICE_IN * 0.1, PRICE_IN * 1.25

# Web search bills per search on top of the tokens its results cost, so a report
# that counted only tokens would quietly understate the research pass.
PRICE_SEARCH = 10 / 1000

_spend: list = []


def _account(message, what: str) -> None:
    usage = getattr(message, "usage", None)
    if usage is None:
        return
    took_in = getattr(usage, "input_tokens", 0) or 0
    took_out = getattr(usage, "output_tokens", 0) or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    wrote = getattr(usage, "cache_creation_input_tokens", 0) or 0
    tools = getattr(usage, "server_tool_use", None)
    searches = getattr(tools, "web_search_requests", 0) or 0 if tools else 0

    cost = (took_in * PRICE_IN + took_out * PRICE_OUT
            + read * PRICE_CACHE_READ + wrote * PRICE_CACHE_WRITE
            + searches * PRICE_SEARCH)
    _spend.append((what, took_in, took_out, read, wrote, searches, cost))

    extra = f" [cache {read:,} read / {wrote:,} written]" if read or wrote else ""
    extra += f" [{searches} searches]" if searches else ""
    print(f"    {took_in:,} in / {took_out:,} out{extra}  (${cost:.3f})",
          file=sys.stderr)


def _spend_summary() -> str:
    """Where the day's money actually went, grouped by pass.

    Printed so the next question about cost is answered with numbers rather
    than an estimate — particularly which pass dominates, since that is the
    only one worth optimising.
    """
    if not _spend:
        return ""
    groups: dict = {}
    counts: dict = {}
    for what, *numbers in _spend:
        key = what.split(" · ")[0]           # fold the nine per-story calls
        got = groups.setdefault(key, [0, 0, 0, 0, 0, 0.0])
        for i, value in enumerate(numbers):
            got[i] += value
        counts[key] = counts.get(key, 0) + 1

    lines, total = ["", "Tokens and cost:"], 0.0
    for key, (took_in, took_out, read, wrote, searches, cost) in groups.items():
        total += cost
        times = f" x{counts[key]}" if counts[key] > 1 else ""
        note = ""
        if read or wrote:
            note = f"  cache {read:,}r/{wrote:,}w"
        if searches:
            note += f"  {searches} searches"
        lines.append(f"  {key + times:<24} {took_in:>9,} in  {took_out:>8,} out"
                     f"  ${cost:5.2f}{note}")
    lines.append(f"  {'total':<24} {'':>9} {'':>13}  ${total:5.2f}")
    return "\n".join(lines)


def _guard(message, what: str):
    _account(message, what)
    if message.stop_reason == "refusal":
        detail = getattr(message.stop_details, "explanation", "") or ""
        raise SystemExit(f"{what} was declined: {detail}")
    if message.stop_reason == "max_tokens":
        # Worth failing loudly on, because structured output makes running out
        # of room look like success: generation stops, the API closes the JSON
        # to satisfy the schema, and what lands is a parseable object whose
        # fields are empty strings and whose arrays hold one empty item. The
        # schema cannot object — minItems above 1 is not accepted — so nothing
        # downstream would notice a page of blank stories.
        raise SystemExit(
            f"{what} hit the token ceiling and was cut off mid-answer. "
            f"Raise max_tokens rather than keeping the truncated result."
        )
    return message


def _shortfall(payload: dict, schema: dict, fields) -> str | None:
    """What is wrong with this answer, in a sentence — or None if nothing is.

    Two ways an answer can disappoint, and both have been seen in a real run:

    Short. The authored schema asks for two questions, two sides each, three
    arguments a side. api_schema has to strip those bounds on the way out, so
    nothing at the far end enforces them, and one call in nine came back with a
    single question carrying a single side — the least the stripped schema
    allows. Validating the reply against the schema as written puts the bounds
    back where they can still be checked, without stating any count twice.

    Hollow. Every field present and empty. jsonschema cannot see that, because
    an empty string is a perfectly good string, so it is checked separately.
    """
    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "the answer"
        return f"{where}: {exc.message}"

    empty = _hollow_field(payload, fields)
    return f"{empty!r} came back empty" if empty else None


# Seen in a real answer: rather than leaving a field empty, the model wrote the
# word "placeholder" into the word bank and every part of the question. Counting
# would catch that particular reply, which was also short — but two questions
# both reading "placeholder" would count as two, so treat the word itself as
# nothing said.
FILLER = {"placeholder", "tbd", "n/a", "todo", "..."}


def _hollow_field(obj: dict, fields) -> str | None:
    """The name of the first field that came back saying nothing, if any.

    A response can satisfy the schema and still say nothing: every required key
    is present, the strings are empty and the arrays hold one empty item, which
    is the least the schema can demand now that minItems above 1 is rejected.
    Nothing downstream would notice, so it is checked here.
    """
    def leaves(value):
        """Every string under a field, however deeply it is nested.

        The text that matters sits two or three levels down — a word bank entry
        holds a term and a definition, each of which holds one string per
        language — so a check that only looked at the top level would see a
        populated list and pass a word bank reading "placeholder".
        """
        if isinstance(value, dict):
            for item in value.values():
                yield from leaves(item)
        elif isinstance(value, list):
            for item in value:
                yield from leaves(item)
        else:
            yield value

    for field in fields:
        found = list(leaves(obj.get(field)))
        if not found or any(not str(v or "").strip() or str(v).strip().lower() in FILLER
                            for v in found):
            return field
    return None


def written(client, cfg, story: dict, band_key: str, attempts: int = 3) -> dict:
    """One story, written for one band, retried while it comes back blank.

    A hollow answer is worth one more try rather than the whole day: the earlier
    runs showed the same request succeeding for two bands and emptying out for
    the third, so it is variance in a single call, not a request that can never
    work.
    """
    what = f"Band {band_key} · {story['slug']}"
    schema = band_schema(cfg, band_key)
    for attempt in range(1, attempts + 1):
        payload = structured(client, cfg, writing_policy(cfg, band_key),
                             band_prompt(story, band_key), schema, what)
        problem = _shortfall(payload, schema, PER_BAND)
        if problem is None:
            return payload
        print(f"  {what}: {problem}, retrying ({attempt}/{attempts})",
              file=sys.stderr)

    raise SystemExit(f"{what} fell short {attempts} times running: {problem}")


def _log_searches(message) -> None:
    """Print the searches the model actually chose to run.

    max_uses is a ceiling, not a plan: the queries are written by the model as
    it goes, each one decided after seeing what the last returned, and they
    differ every day. Without this there is no way to tell whether a run used
    three searches or twenty, or whether the twentieth was still finding
    anything the first nineteen had not — which is the only honest basis for
    deciding where the ceiling belongs.
    """
    queries = [
        (block.input or {}).get("query")
        for block in getattr(message, "content", [])
        if getattr(block, "type", "") == "server_tool_use"
        and getattr(block, "name", "") == "web_search"
    ]
    for i, query in enumerate(q for q in queries if q):
        print(f"    search {i + 1}: {query}", file=sys.stderr)


def research(client, cfg, prompt: str, max_restarts: int = 4) -> str:
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 20}]

    for attempt in range(max_restarts + 1):
        with client.messages.stream(
            model=MODEL, max_tokens=64000, system=base_policy(cfg),
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            # This pass is three quarters of the day's bill, and almost all of
            # it is input: search results are charged as input tokens on every
            # iteration that re-reads them, so twenty searches pay for the
            # earlier ones over and over. A cache hit costs a tenth of that.
            # Automatic caching is enough here — there is one long conversation
            # with a growing prefix, which is exactly the shape it handles.
            cache_control={"type": "ephemeral"},
            tools=tools, messages=messages,
        ) as stream:
            message = _guard(stream.get_final_message(), "Research")

        _log_searches(message)

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
        model=MODEL, max_tokens=64000, system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema",
                                  "schema": api_schema(schema)}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = _guard(stream.get_final_message(), what)
    return json.loads(_text_of(message))


# --------------------------------------------------------------------------- assembly


def build_edition(cfg, skeleton: dict, writing: dict, date_str: str, start, end) -> dict:
    stories = sorted(skeleton["stories"], key=lambda s: s.get("rank", 99))

    for i, story in enumerate(stories, 1):
        story["rank"] = i
        # Each piece of writing was requested for one story and one band, so
        # there is nothing left to match up — no slug lookup that can miss, and
        # no positional fallback that can quietly attach a band to the wrong
        # story.
        by_band = writing[story["slug"]]
        story["versions"] = {band: {k: by_band[band][k] for k in PER_BAND}
                             for band in appconfig.AGE_BANDS if band in by_band}
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
        "generator": (f"{MODEL} (research + skeleton + "
                      f"{len(appconfig.AGE_BANDS)} bands x {N} stories)"),
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
    skel_schema = skeleton_schema(cfg)
    skeleton = structured(client, cfg, base_policy(cfg), skeleton_prompt(brief),
                          skel_schema, "Skeleton")
    problem = _shortfall(skeleton, skel_schema, ())
    if problem is None:
        for story in skeleton["stories"]:
            problem = _hollow_field(story, ("slug", "facts"))
            problem = f"story {story.get('rank')}: empty {problem!r}" if problem else None
            if problem:
                break
    if problem:
        raise SystemExit(f"Skeleton fell short — {problem}")
    for s in sorted(skeleton["stories"], key=lambda s: s["rank"]):
        print(f"  {s['rank']}. [{s['category']}·{s['region']}] {s['slug']}")

    ordered = sorted(skeleton["stories"], key=lambda s: s.get("rank", 99))
    writing = {}
    for i, band_key in enumerate(appconfig.AGE_BANDS, 1):
        for j, story in enumerate(ordered, 1):
            print(f"Pass 3.{i}.{j} — writing {story['slug']} for {band_key}…")
            writing.setdefault(story["slug"], {})[band_key] = written(
                client, cfg, story, band_key)

    edition = build_edition(cfg, skeleton, writing, date_str, start, end)
    text = json.dumps(edition, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        print(text)
        print(_spend_summary(), file=sys.stderr)
        return

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    lang = cfg.primary_language
    for story in edition["stories"]:
        head = story["versions"].get(cfg.band, {}).get("headline", {}).get(lang, "")
        print(f"  {story['rank']}. [{story['category']}] {head}")
    print(_spend_summary())


if __name__ == "__main__":
    main()
