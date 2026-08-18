#!/usr/bin/env python3
"""Shared configuration and catalogues for Daily News for Kids.

Everything a family can change lives in config.toml at the repository root.
This module loads it, validates it loudly, and exposes the vocabularies the
other scripts render from, so adding a beat or a region is a one-place change.
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
    "en": "World news your child can actually read — and argue about.",
    "zh": "孩子真正读得懂、还想争一争的每日世界新闻。",
}

LANGUAGES = {"en": "English", "zh": "中文"}

# --------------------------------------------------------------------- beats
# Each beat carries its own colour in both themes. A story's card, chips, rules
# and numerals all take this accent, so the colour says what kind of news it is
# before a word is read. Order here is the order shown in the setup form.

CATEGORIES: dict[str, dict] = {
    "politics": {
        "label": {"en": "Politics", "zh": "政治"},
        "light": ("#a4243b", "#fbeef0"), "dark": ("#f0899c", "#2a171c"),
        "hint": {"en": "Governments, elections, laws, war and peace.",
                 "zh": "政府、选举、法律、战争与和平。"},
    },
    "society": {
        "label": {"en": "Society", "zh": "社会"},
        "light": ("#1a6b4a", "#eaf4ef"), "dark": ("#5cc79b", "#12251d"),
        "hint": {"en": "How people live: cities, families, migration, justice.",
                 "zh": "人怎么生活：城市、家庭、移民、公平。"},
    },
    "business": {
        "label": {"en": "Business", "zh": "财经"},
        "light": ("#8a5a0f", "#f8f0e2"), "dark": ("#dfae5c", "#262013"),
        "hint": {"en": "Money, jobs, companies, prices, trade.",
                 "zh": "钱、工作、公司、物价、贸易。"},
    },
    "tech": {
        "label": {"en": "Tech", "zh": "科技"},
        "light": ("#4b3ba8", "#eeecfa"), "dark": ("#a89bf7", "#1d1a2e"),
        "hint": {"en": "Computers, AI, phones, robots, the internet.",
                 "zh": "电脑、人工智能、手机、机器人、互联网。"},
    },
    "science": {
        "label": {"en": "Science", "zh": "科学"},
        "light": ("#0f6a76", "#e6f2f4"), "dark": ("#5ec4d2", "#10262a"),
        "hint": {"en": "Discoveries, space, medicine, how things work.",
                 "zh": "新发现、太空、医学、事物的原理。"},
    },
    "environment": {
        "label": {"en": "Environment", "zh": "环境"},
        "light": ("#4a6b12", "#f0f4e4"), "dark": ("#a8c766", "#1c2412"),
        "hint": {"en": "Climate, animals, oceans, energy, weather.",
                 "zh": "气候、动物、海洋、能源、天气。"},
    },
    "sports": {
        "label": {"en": "Sports", "zh": "体育"},
        "light": ("#b0511a", "#fceee5"), "dark": ("#f5a173", "#2c1a11"),
        "hint": {"en": "Games, records, teams, the Olympics.",
                 "zh": "比赛、纪录、球队、奥运会。"},
    },
    "arts": {
        "label": {"en": "Arts & Culture", "zh": "艺术与文化"},
        "light": ("#9c2a7a", "#fbecf6"), "dark": ("#ef8fd0", "#2a1526"),
        "hint": {"en": "Music, film, books, museums, design.",
                 "zh": "音乐、电影、书、博物馆、设计。"},
    },
    "health": {
        "label": {"en": "Health", "zh": "健康"},
        "light": ("#1c5aa8", "#e8f0fb"), "dark": ("#85b3f0", "#131f2e"),
        "hint": {"en": "Bodies, illness, food, sleep, sport science.",
                 "zh": "身体、疾病、饮食、睡眠、运动科学。"},
    },
    "education": {
        "label": {"en": "Education", "zh": "教育"},
        "light": ("#6b4a1f", "#f5efe6"), "dark": ("#d4b183", "#241c12"),
        "hint": {"en": "Schools, exams, universities, learning.",
                 "zh": "学校、考试、大学、学习。"},
    },
}

# -------------------------------------------------------------------- regions
# GLOBAL is both a selectable shorthand meaning "everywhere" and the tag put on
# a story that genuinely belongs to no single country.

REGIONS: dict[str, dict] = {
    "US": {"label": {"en": "United States", "zh": "美国"}},
    "CN": {"label": {"en": "China", "zh": "中国"}},
    "CA": {"label": {"en": "Canada", "zh": "加拿大"}},
    "EU": {"label": {"en": "Europe", "zh": "欧洲"}},
    "JPKR": {"label": {"en": "Japan & Korea", "zh": "日本与韩国"}},
    "ANZ": {"label": {"en": "Australia & NZ", "zh": "澳洲与新西兰"}},
    "SEA": {"label": {"en": "Southeast Asia", "zh": "东南亚"}},
    "SASIA": {"label": {"en": "South Asia", "zh": "南亚"}},
    "LATAM": {"label": {"en": "Latin America", "zh": "拉丁美洲"}},
    "MEA": {"label": {"en": "Middle East & Africa", "zh": "中东与非洲"}},
    "GLOBAL": {"label": {"en": "Global", "zh": "全球"}},
}

# Every region except the GLOBAL shorthand itself.
COUNTRY_REGIONS = [k for k in REGIONS if k != "GLOBAL"]

MIN_COUNT, MAX_COUNT = 3, 10
MIN_AGE, MAX_AGE = 5, 18


# ------------------------------------------------------------ reading profile

def reading_profile(age: int) -> dict:
    """Turn an age into concrete writing instructions.

    The bands are deliberately coarse. What changes with age is sentence
    length, how much abstraction a reader can hold, and how much scaffolding a
    word needs — not how serious the news is allowed to be.
    """
    if age <= 8:
        return {
            "band": "6-8",
            "paragraphs": "3 to 4 very short paragraphs",
            "sentences": "Short sentences, one idea each. Almost never a subclause.",
            "words": 2,
            "voice": (
                "Explain as you would to a curious 7-year-old who reads well but "
                "has almost no background knowledge. Anchor every abstract thing "
                "to something they can touch, count, or see in their own week. "
                "Numbers larger than a few thousand need a physical comparison."
            ),
            "questions": (
                "Questions must be answerable from feelings and fairness, not "
                "from knowledge they do not have — 'is that fair?', 'what would "
                "you do?'. Still genuinely two-sided."
            ),
        }
    if age <= 11:
        return {
            "band": "9-11",
            "paragraphs": "4 to 5 short paragraphs",
            "sentences": "Mostly short sentences. One clause of nuance at a time.",
            "words": 3,
            "voice": (
                "Explain as you would to a curious 10-year-old. They can follow "
                "cause and effect across a few steps, but every institution, "
                "number, and piece of jargon still needs unpacking the first time."
            ),
            "questions": (
                "Questions about fairness, trade-offs, and what they would do — "
                "concrete enough to picture, open enough to disagree about."
            ),
        }
    if age <= 14:
        return {
            "band": "12-14",
            "paragraphs": "4 to 6 paragraphs",
            "sentences": "Varied sentence length. Nuance is welcome if it is earned.",
            "words": 3,
            "voice": (
                "Explain as you would to a bright, sceptical 13-year-old. They can "
                "hold a system in mind — incentives, second-order effects, competing "
                "interests — but jargon still gets defined the first time it appears."
            ),
            "questions": (
                "Questions about trade-offs, incentives, and unintended consequences. "
                "They should be hard enough that a smart adult would pause."
            ),
        }
    return {
        "band": "15-18",
        "paragraphs": "5 to 6 paragraphs",
        "sentences": "Adult sentence rhythm. Complexity is fine; padding is not.",
        "words": 3,
        "voice": (
            "Write close to good adult journalism, minus the assumed background. "
            "Assume real reasoning ability and no institutional knowledge. Do not "
            "simplify the substance — only the scaffolding."
        ),
        "questions": (
            "Questions that reach the actual disagreement among informed adults — "
            "about values and trade-offs, not about facts."
        ),
    }


# ---------------------------------------------------------------------- model

@dataclass
class Config:
    child_name: str
    age: int
    count: int
    categories: list
    regions: list
    languages: list
    timezone: str
    hour: int
    site_url: str
    raw: dict = field(default_factory=dict)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def profile(self) -> dict:
        return reading_profile(self.age)

    @property
    def primary_language(self) -> str:
        return self.languages[0]

    def label(self, kind: str, key: str, lang: str) -> str:
        table = CATEGORIES if kind == "category" else REGIONS
        entry = table.get(key)
        if not entry:
            return key
        return entry["label"].get(lang) or entry["label"]["en"]

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

    count = edition.get("count", 3)
    _require(isinstance(count, int) and MIN_COUNT <= count <= MAX_COUNT,
             f"edition.count must be from {MIN_COUNT} to {MAX_COUNT} (got {count!r}). "
             "More than 10 stops being a digest.")

    categories = list(edition.get("categories") or [])
    _require(bool(categories), "edition.categories cannot be empty")
    unknown = [c for c in categories if c not in CATEGORIES]
    _require(not unknown,
             f"unknown category {unknown}. Choose from: {', '.join(CATEGORIES)}")

    regions = list(edition.get("regions") or [])
    _require(bool(regions), "edition.regions cannot be empty")
    unknown = [r for r in regions if r not in REGIONS]
    _require(not unknown,
             f"unknown region {unknown}. Choose from: {', '.join(REGIONS)}")
    # "Global" is shorthand for the whole list rather than a region of its own.
    if "GLOBAL" in regions:
        regions = list(COUNTRY_REGIONS)

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
        count=count,
        categories=categories,
        regions=regions,
        languages=languages,
        timezone=timezone,
        hour=hour,
        site_url=str(site.get("url", "") or ""),
        raw=data,
    )


def category_label(key: str, lang: str) -> str:
    entry = CATEGORIES.get(key)
    return (entry["label"].get(lang) or entry["label"]["en"]) if entry else key


def region_label(key: str, lang: str) -> str:
    entry = REGIONS.get(key)
    return (entry["label"].get(lang) or entry["label"]["en"]) if entry else key


def beat_colors(theme: str = "light") -> dict:
    """{beat: (accent, tint)} for one theme — used by the poster and the email,
    which cannot use CSS custom properties."""
    return {k: tuple(v[theme]) for k, v in CATEGORIES.items()}


def resolve_window(cfg: "Config", date_str: str | None = None,
                   now: "datetime | None" = None) -> tuple:
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
