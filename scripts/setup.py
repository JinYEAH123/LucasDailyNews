#!/usr/bin/env python3
"""Interactive setup — writes config.toml by asking a few questions.

    python3 scripts/setup.py

Prefer the form at docs/setup.html if you would rather click than type; this is
the same questions for people who live in a terminal.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import appconfig

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.toml"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)
    return answer or default


def ask_int(prompt: str, default: int, low: int, high: int) -> int:
    while True:
        raw = ask(f"{prompt} ({low}-{high})", str(default))
        try:
            value = int(raw)
        except ValueError:
            print(f"  Needs to be a whole number from {low} to {high}.")
            continue
        if low <= value <= high:
            return value
        print(f"  Needs to be from {low} to {high}.")


def ask_multi(prompt: str, options: dict, default: list, extra: str = "") -> list:
    """Numbered multi-select. Blank keeps the default."""
    keys = list(options)
    print(f"\n{prompt}")
    for i, key in enumerate(keys, 1):
        mark = "x" if key in default else " "
        label = options[key]["label"]["en"]
        zh = options[key]["label"].get("zh", "")
        print(f"  [{mark}] {i:2}. {label}" + (f"  ({zh})" if zh else ""))
    if extra:
        print(f"      {extra}")
    while True:
        raw = ask("Numbers, comma separated", ",".join(
            str(keys.index(k) + 1) for k in default if k in keys))
        picked, bad = [], []
        for chunk in raw.replace(" ", "").split(","):
            if not chunk:
                continue
            if chunk.isdigit() and 1 <= int(chunk) <= len(keys):
                key = keys[int(chunk) - 1]
                if key not in picked:
                    picked.append(key)
            else:
                bad.append(chunk)
        if bad:
            print(f"  Not on the list: {', '.join(bad)}")
            continue
        if not picked:
            print("  Pick at least one.")
            continue
        return picked


def guess_timezone() -> str:
    """Best guess at the local zone, so most people can press Enter."""
    try:
        name = datetime.now().astimezone().tzname()
        # tzname gives an abbreviation, not an IANA id; try the system link.
        link = Path("/etc/localtime")
        if link.is_symlink():
            parts = link.resolve().parts
            if "zoneinfo" in parts:
                idx = parts.index("zoneinfo")
                candidate = "/".join(parts[idx + 1:])
                ZoneInfo(candidate)
                return candidate
        del name
    except (OSError, ValueError, ZoneInfoNotFoundError):
        pass
    return "America/Vancouver"


def toml_list(values: list) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


def main() -> None:
    print("\nDaily News for Kids — setup")
    print(appconfig.SLOGAN["en"])
    print("-" * 58)

    current = None
    if CONFIG.exists():
        try:
            current = appconfig.load(CONFIG)
            print("Found an existing config.toml; its values are the defaults.\n")
        except SystemExit:
            print("Found a config.toml but could not read it; starting fresh.\n")

    name = ask("Child's name (blank to leave it off the page)",
               current.child_name if current else "")
    age = ask_int("Age — this sets how the news is written",
                  current.age if current else 12, appconfig.MIN_AGE, appconfig.MAX_AGE)
    count = ask_int("Stories per day", current.count if current else 3,
                    appconfig.MIN_COUNT, appconfig.MAX_COUNT)

    categories = ask_multi(
        "Which beats should it cover?",
        appconfig.CATEGORIES,
        current.categories if current else ["politics", "society", "business", "tech"],
    )

    region_default = current.regions if current else ["US", "CN"]
    if current and set(current.regions) == set(appconfig.COUNTRY_REGIONS):
        region_default = ["GLOBAL"]
    regions = ask_multi(
        "Which parts of the world?",
        appconfig.REGIONS,
        region_default,
        extra="Global (the last one) means all of them.",
    )
    if "GLOBAL" in regions:
        regions = ["GLOBAL"]

    languages = ask_multi(
        "Which languages?",
        {k: {"label": {"en": v}} for k, v in appconfig.LANGUAGES.items()},
        current.languages if current else ["en"],
    )

    print()
    timezone = ask("Time zone (IANA name)",
                   current.timezone if current else guess_timezone())
    while True:
        try:
            ZoneInfo(timezone)
            break
        except (ZoneInfoNotFoundError, ValueError):
            print("  Not a known zone. Examples: America/New_York, Europe/London, Asia/Shanghai")
            timezone = ask("Time zone (IANA name)", "America/Vancouver")

    hour = ask_int("Hour of day to publish, 24-hour clock",
                   current.hour if current else 17, 0, 23)
    url = ask("Site address (your GitHub Pages URL, can be filled in later)",
              current.site_url if current else "")

    text = f"""# Daily News for Kids — written by scripts/setup.py
# Re-run that script, or edit by hand, whenever you want to change something.

[child]
name = "{name}"
age = {age}

[edition]
count = {count}
categories = {toml_list(categories)}
regions = {toml_list(regions)}
languages = {toml_list(languages)}

[schedule]
timezone = "{timezone}"
hour = {hour}

[site]
url = "{url}"
"""

    print("\n" + "-" * 58)
    print(text)
    print("-" * 58)

    if CONFIG.exists() and ask("Overwrite the existing config.toml? (y/n)", "y").lower() != "y":
        print("Left it alone. Nothing written.")
        return

    CONFIG.write_text(text, encoding="utf-8")

    # Prove it round-trips before telling anyone it worked.
    cfg = appconfig.load(CONFIG)
    print(f"\nWrote {CONFIG.relative_to(ROOT)} and read it back cleanly.")
    print(f"  {cfg.count} stories a day for a {cfg.age}-year-old")
    print(f"  beats:   {', '.join(appconfig.category_label(c, 'en') for c in cfg.categories)}")
    print(f"  regions: {', '.join(appconfig.region_label(r, 'en') for r in cfg.regions)}")
    print(f"  each day at {cfg.hour:02d}:00 {cfg.timezone}")
    print("\nNext: python3 scripts/render_site.py")


if __name__ == "__main__":
    main()
