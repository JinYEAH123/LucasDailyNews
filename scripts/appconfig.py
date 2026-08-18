#!/usr/bin/env python3
"""Shared configuration and catalogues for Daily News for Kids.

The product is deliberately narrow: three stories a day, drawn from five beats,
centred on the US and China plus anything genuinely global. None of that is a
reader's choice — it is the editorial line.

The one thing a reader does choose is the **age band**. Every edition is written
three times, at three reading levels, so switching bands on the page is instant
and needs no server.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"

APP_NAME = {"en": "Daily News for Kids", "zh": "少年每日新闻"}
SLOGAN = {
    "en": "World news worth arguing about.",
    "zh": "世界新闻，值得争一争。",
}

LANGUAGES = {"en": "English", "zh": "中文"}

STORIES_PER_DAY = 3

# --------------------------------------------------------------------- beats
# Fixed. A reader cannot filter these — three stories a day is already a
# selection, and letting people switch beats off would mostly produce a blank
# page. Colour is what the beat carries on the page.

CATEGORIES: dict[str, dict] = {
    "politics": {
        "label": {"en": "Politics", "zh": "政治"},
        "light": ("#a4243b", "#fbeef0"), "dark": ("#f0899c", "#2a171c"),
    },
    "society": {
        "label": {"en": "Society", "zh": "社会"},
        "light": ("#1a6b4a", "#eaf4ef"), "dark": ("#5cc79b", "#12251d"),
    },
    "business": {
        "label": {"en": "Business & Economy", "zh": "财经"},
        "light": ("#8a5a0f", "#f8f0e2"), "dark": ("#dfae5c", "#262013"),
    },
    "tech": {
        "label": {"en": "Tech", "zh": "科技"},
        "light": ("#4b3ba8", "#eeecfa"), "dark": ("#a89bf7", "#1d1a2e"),
    },
    "science": {
        "label": {"en": "Science", "zh": "科学"},
        "light": ("#0f6a76", "#e6f2f4"), "dark": ("#5ec4d2", "#10262a"),
    },
}

# -------------------------------------------------------------------- regions
# The US and China are the centre of gravity; GLOBAL is the escape hatch the
# editorial policy needs for news too big to belong to one country.

REGIONS: dict[str, dict] = {
    "US": {"label": {"en": "United States", "zh": "美国"}},
    "CN": {"label": {"en": "China", "zh": "中国"}},
    "GLOBAL": {"label": {"en": "Global", "zh": "全球"}},
}

# ----------------------------------------------------------------- age bands
# Three bands, written separately. What changes is sentence length, how much
# scaffolding a fact needs, and how hard the questions are — never how serious
# the news is allowed to be.

AGE_BANDS: dict[str, dict] = {
    "6-11": {
        "label": {"en": "Ages 6–11", "zh": "6–11 岁"},
        "short": {"en": "6–11", "zh": "6–11"},
        "range": (5, 11),
        "paragraphs": "3 to 4 very short paragraphs",
        "sentences": "Short sentences, one idea each. Almost never a subclause.",
        "words": 2,
        "voice": (
            "Write for a curious 9-year-old who reads well but has almost no "
            "background knowledge. Anchor every abstract thing to something they "
            "can touch, count, or see in their own week. Any number bigger than a "
            "few thousand needs a physical comparison. Name a country or a leader "
            "the way you would introduce a stranger — they may never have heard of "
            "either."
        ),
        "questions": (
            "Questions answerable from fairness and feelings rather than knowledge "
            "they do not have — 'is that fair?', 'what would you do?'. Still "
            "genuinely two-sided, and the two sides still argued properly."
        ),
    },
    "12-15": {
        "label": {"en": "Ages 12–15", "zh": "12–15 岁"},
        "short": {"en": "12–15", "zh": "12–15"},
        "range": (12, 15),
        "paragraphs": "4 to 6 paragraphs",
        "sentences": "Varied sentence length. Nuance is welcome when it is earned.",
        "words": 3,
        "voice": (
            "Write for a bright, sceptical 13-year-old. They can hold a system in "
            "mind — incentives, second-order effects, competing interests — but "
            "every institution and piece of jargon still gets unpacked the first "
            "time it appears."
        ),
        "questions": (
            "Questions about trade-offs, incentives, and unintended consequences, "
            "hard enough that a thoughtful adult would pause before answering."
        ),
    },
    "16+": {
        "label": {"en": "Ages 16+", "zh": "16 岁以上"},
        "short": {"en": "16+", "zh": "16+"},
        "range": (16, 18),
        "paragraphs": "5 to 6 paragraphs",
        "sentences": "Adult sentence rhythm. Complexity is fine; padding is not.",
        "words": 3,
        "voice": (
            "Write close to good adult journalism, minus the assumed background. "
            "Assume real reasoning ability and no institutional knowledge. Do not "
            "simplify the substance — only the scaffolding. Name the mechanism, "
            "not just the outcome."
        ),
        "questions": (
            "Questions that reach the actual disagreement among informed adults — "
            "about values and trade-offs, not about facts."
        ),
    },
}

DEFAULT_BAND = "12-15"

MIN_AGE, MAX_AGE = 5, 18


def tz_abbrev(cfg: "Config", when=None) -> str:
    """The zone's abbreviation at a moment — PDT, PST, GMT, BST, CST, JST.

    Taken from the moment rather than the zone, because half of them change
    twice a year and a label that says PDT in December is simply wrong.
    """
    from datetime import datetime

    moment = when or datetime.now(cfg.tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=cfg.tz)
    else:
        # A fixed UTC offset (e.g. parsed from "...-07:00") carries no zone
        # name, so strftime("%Z") would just echo the offset back. Re-anchor
        # to the configured zone, which knows PDT from PST.
        moment = moment.astimezone(cfg.tz)
    return moment.strftime("%Z") or cfg.timezone.split("/")[-1].replace("_", " ")


def band_for_age(age: int) -> str:
    """Which band an age falls into. Used only to pick the default view."""
    for key, band in AGE_BANDS.items():
        low, high = band["range"]
        if low <= age <= high:
            return key
    return DEFAULT_BAND


def band_label(key: str, lang: str) -> str:
    band = AGE_BANDS.get(key)
    return (band["label"].get(lang) or band["label"]["en"]) if band else key


def category_label(key: str, lang: str) -> str:
    entry = CATEGORIES.get(key)
    return (entry["label"].get(lang) or entry["label"]["en"]) if entry else key


def region_label(key: str, lang: str) -> str:
    entry = REGIONS.get(key)
    return (entry["label"].get(lang) or entry["label"]["en"]) if entry else key


def beat_colors(theme: str = "light") -> dict:
    """{beat: (accent, tint)} for one theme — for the poster and the email,
    which cannot use CSS custom properties."""
    return {k: tuple(v[theme]) for k, v in CATEGORIES.items()}


# ---------------------------------------------------------------------- model

@dataclass
class Config:
    child_name: str
    age: int
    languages: list
    timezone: str
    hour: int
    site_url: str
    raw: dict = field(default_factory=dict)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def band(self) -> str:
        """The band shown by default — everything is generated regardless."""
        return band_for_age(self.age)

    @property
    def primary_language(self) -> str:
        return self.languages[0]

    def title(self, lang: str) -> str:
        return APP_NAME.get(lang, APP_NAME["en"])

    def slogan(self, lang: str) -> str:
        return SLOGAN.get(lang, SLOGAN["en"])


class ConfigError(SystemExit):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(f"config.toml: {message}")


def load(path: Path | None = None) -> Config:
    path = path or CONFIG_PATH
    if not path.exists():
        raise ConfigError(
            f"{path} not found.\n"
            "Run `python3 scripts/setup.py` to create one, or copy config.example.toml."
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc

    child = data.get("child", {})
    edition = data.get("edition", {})
    schedule = data.get("schedule", {})
    site = data.get("site", {})

    age = child.get("age", 12)
    _require(isinstance(age, int) and MIN_AGE <= age <= MAX_AGE,
             f"child.age must be a whole number from {MIN_AGE} to {MAX_AGE} (got {age!r})")

    languages = list(edition.get("languages") or ["en"])
    unknown = [l for l in languages if l not in LANGUAGES]
    _require(not unknown, f"unknown language {unknown}. Choose from: en, zh")
    _require(bool(languages), "edition.languages cannot be empty")

    timezone = schedule.get("timezone", "America/Vancouver")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(
            f"schedule.timezone {timezone!r} is not a known IANA time zone. "
            "Use a name like 'America/Vancouver', 'Europe/London', 'Asia/Shanghai'."
        ) from exc

    hour = schedule.get("hour", 17)
    _require(isinstance(hour, int) and 0 <= hour <= 23,
             f"schedule.hour must be 0-23 in {timezone} (got {hour!r})")

    return Config(
        child_name=str(child.get("name", "") or ""),
        age=age,
        languages=languages,
        timezone=timezone,
        hour=hour,
        site_url=str(site.get("url", "") or ""),
        raw=data,
    )


def resolve_window(cfg: "Config", date_str: str | None = None,
                   now=None) -> tuple:
    """Return (edition_date, window_start, window_end) in the family's zone.

    The edition dated D covers D-1 at the cutoff hour through D at the cutoff
    hour. Before the cutoff, the newest complete edition is still yesterday's.

    Lives here rather than in generate_edition.py so the scheduled workflow can
    work out which edition is due without importing the Anthropic SDK.
    """
    from datetime import datetime, timedelta, time as dtime

    tz = cfg.tz
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now = now or datetime.now(tz)
        day = now.date() if now.hour >= cfg.hour else (now - timedelta(days=1)).date()

    end = datetime.combine(day, dtime(cfg.hour, 0), tzinfo=tz)
    return day.isoformat(), end - timedelta(days=1), end
