#!/usr/bin/env python3
"""Interactive setup — writes config.toml by asking a few questions.

    python3 scripts/setup.py

Short on purpose. Beats, regions and story count are the editorial line rather
than settings, so the only questions are who is reading, in what language, and
when the edition lands.
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
        return input(f"{prompt}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)


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


def ask_languages(default: list) -> list:
    keys = list(appconfig.LANGUAGES)
    print("\nWhich languages should each edition be written in?")
    for i, k in enumerate(keys, 1):
        mark = "x" if k in default else " "
        print(f"  [{mark}] {i}. {appconfig.LANGUAGES[k]}")
    while True:
        raw = ask("Numbers, comma separated",
                  ",".join(str(keys.index(k) + 1) for k in default if k in keys))
        picked = []
        for chunk in raw.replace(" ", "").split(","):
            if chunk.isdigit() and 1 <= int(chunk) <= len(keys):
                key = keys[int(chunk) - 1]
                if key not in picked:
                    picked.append(key)
        if picked:
            return picked
        print("  Pick at least one.")


def guess_timezone() -> str:
    try:
        link = Path("/etc/localtime")
        if link.is_symlink():
            parts = link.resolve().parts
            if "zoneinfo" in parts:
                candidate = "/".join(parts[parts.index("zoneinfo") + 1:])
                ZoneInfo(candidate)
                return candidate
    except (OSError, ValueError, ZoneInfoNotFoundError):
        pass
    return "America/Vancouver"


def main() -> None:
    print("\nDaily News for Kids — setup")
    print(appconfig.SLOGAN["en"])
    print("-" * 60)
    print("Three stories a day, from politics, society, business, tech and")
    print("science, centred on the US and China. That part is fixed.")
    print("-" * 60)

    current = None
    if CONFIG.exists():
        try:
            current = appconfig.load(CONFIG)
            print("Found an existing config.toml; its values are the defaults.\n")
        except SystemExit:
            print("Found a config.toml but could not read it; starting fresh.\n")

    name = ask("Child's name (blank to leave it off the page)",
               current.child_name if current else "")
    age = ask_int("Age", current.age if current else 12,
                  appconfig.MIN_AGE, appconfig.MAX_AGE)
    band = appconfig.band_for_age(age)
    print(f"  Every edition is written for all three levels; the page will open "
          f"on {appconfig.band_label(band, 'en')}.")

    languages = ask_languages(current.languages if current else ["en"])

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

[child]
name = "{name}"
age = {age}

[edition]
languages = [{", ".join(f'"{l}"' for l in languages)}]

[schedule]
timezone = "{timezone}"
hour = {hour}

[site]
url = "{url}"
"""

    print("\n" + "-" * 60)
    print(text)
    print("-" * 60)

    if CONFIG.exists() and ask("Overwrite the existing config.toml? (y/n)", "y").lower() != "y":
        print("Left it alone. Nothing written.")
        return

    CONFIG.write_text(text, encoding="utf-8")

    # Prove it round-trips before saying it worked.
    cfg = appconfig.load(CONFIG)
    print(f"\nWrote {CONFIG.relative_to(ROOT)} and read it back cleanly.")
    print(f"  {appconfig.STORIES_PER_DAY} stories a day, written for "
          f"{', '.join(appconfig.AGE_BANDS)}")
    print(f"  page opens on {appconfig.band_label(cfg.band, 'en')} in "
          f"{'/'.join(cfg.languages)}")
    print(f"  each day at {cfg.hour:02d}:00 {cfg.timezone}")
    print("\nNext: python3 scripts/render_site.py")


if __name__ == "__main__":
    main()
