#!/usr/bin/env python3
"""Render one edition as a tall shareable image for WeChat Moments.

The poster is a deliberately reduced view: rank, beat, headline, the one-
paragraph summary, and the three dinner questions. Everything else — the full
rewrite, the word bank, background and further reading, the two-sided hints,
the videos — sits behind the QR code at the bottom. A Moments image is an
invitation, not the article.

Output goes to docs/posters/<date>-<lang>.png so it ships with the site and can
be linked from the edition page.

Usage:
    python3 scripts/build_poster.py                     # newest edition, Chinese
    python3 scripts/build_poster.py --lang en
    python3 scripts/build_poster.py --date 2026-08-17 --both
    python3 scripts/build_poster.py --keep-html         # also write the HTML

Requires: pip install segno playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

import segno

import render_site as site

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"
POSTER_DIR = ROOT / "docs" / "posters"

DEFAULT_SITE_URL = "https://jinyeah123.github.io/LucasDailyNews/"

# Poster geometry. 750 CSS px at 2x gives a 1500 px wide PNG — sharp on a phone
# and well inside what WeChat will show without re-compressing to mush.
WIDTH = 750
SCALE = 2

C = {
    "paper": "#eff2ef",
    "card": "#ffffff",
    "ink": "#101619",
    "ink_soft": "#46545b",
    "ink_faint": "#7a878e",
    "rule": "#d7ded9",
    "rule_soft": "#e7ebe7",
    "chrome": "#26343b",
}

BEAT = {
    "politics": ("#a4243b", "#fbeef0"),
    "society": ("#1a6b4a", "#eaf4ef"),
    "business": ("#8a5a0f", "#f8f0e2"),
    "tech": ("#4b3ba8", "#eeecfa"),
}

T = {
    "title": {"en": "Lucas Daily News", "zh": "Lucas 每日新闻"},
    "tagline": {"en": "Three stories that mattered today", "zh": "今天值得知道的三条新闻"},
    "talk": {"en": "Talk about it at dinner", "zh": "饭桌上聊聊"},
    "scan": {"en": "Scan to read the whole thing", "zh": "扫码读完整版"},
    "scan_sub": {
        "en": "The full rewrite for a 12-year-old, words worth knowing, background "
              "and further reading, videos — and the case for both sides of every "
              "question above.",
        "zh": "为12岁读者改写的完整正文、值得记住的词、背景阅读与延展阅读、视频，"
              "以及上面每个问题正反两方的说法。",
    },
    "footer": {
        "en": "Updated every day at 5:00 PM Vancouver time · English and Chinese",
        "zh": "每天温哥华时间下午 5 点更新 · 中英双语",
    },
}


def t(key: str, lang: str) -> str:
    return T[key][lang]


def pick(value: object, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    return str(value or "")


def e(text: object) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def qr_svg(url: str) -> str:
    """Inline SVG QR, sized by CSS.

    Two details matter and both are easy to get wrong:

    - border=4 is the quiet zone the QR spec requires. Without it the panel's
      padding is all a scanner has to work with, and decoding becomes flaky.
    - segno's svg_inline emits width/height but no viewBox, so a CSS width would
      crop the symbol instead of scaling it. Injecting the viewBox makes the
      symbol scale properly whatever module count today's URL produces.
    """
    qr = segno.make(url, error="m")
    modules = qr.symbol_size(border=4)[0]
    svg = qr.svg_inline(scale=1, border=4, dark=C["ink"], light=None)
    return svg.replace("<svg ", f'<svg viewBox="0 0 {modules} {modules}" ', 1)


# --------------------------------------------------------------------------- html

def story_block(story: dict, lang: str) -> str:
    cat = story.get("category", "politics")
    accent, tint = BEAT.get(cat, BEAT["politics"])
    cat_name = e(pick(site.CATEGORIES.get(cat, {}), lang))
    region = e(pick(site.REGIONS.get(story.get("region", "GLOBAL"), {}), lang))

    questions = story.get("talk_about_it")
    talk = ""
    if isinstance(questions, list) and questions:
        rows = "".join(
            f'<li><span class="qn" style="color:{accent}">{i}</span>'
            f'<span>{e(pick(q.get("question"), lang))}</span></li>'
            for i, q in enumerate(questions, 1)
        )
        talk = (
            f'<div class="talk">'
            f'<p class="talk-label" style="color:{accent}">{e(t("talk", lang))}</p>'
            f"<ul>{rows}</ul></div>"
        )

    return f"""<article class="story">
  <div class="top">
    <span class="rank" style="color:{accent}">{e(story.get('rank', ''))}</span>
    <span class="chip" style="color:{accent};background:{tint}">{cat_name}</span>
    <span class="chip region">{region}</span>
  </div>
  <h2>{e(pick(story.get('headline'), lang))}</h2>
  <p class="hook">{e(pick(story.get('hook'), lang))}</p>
  {talk}
</article>"""


def build_html(edition: dict, lang: str, site_url: str) -> str:
    date_str = edition["date"]
    pretty = e(pick(site.pretty_date(date_str), lang))
    window = e(pick((edition.get("window") or {}).get("label"), lang))
    stories = sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99))
    target = f"{site_url.rstrip('/')}/editions/{date_str}.html"

    serif = "'Fraunces','Iowan Old Style',Georgia,serif"
    sans = ("'Public Sans',-apple-system,'Segoe UI',Roboto,'Noto Sans SC',"
            "'PingFang SC','WenQuanYi Zen Hei',sans-serif")

    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?\
family=Fraunces:opsz,wght@9..144,600;9..144,700&\
family=Public+Sans:wght@400;500;600;700&\
family=Noto+Sans+SC:wght@400;500;700&display=swap">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {WIDTH}px; background: {C['paper']};
    font-family: {sans}; color: {C['ink']};
    -webkit-font-smoothing: antialiased;
  }}
  .sheet {{ padding: 46px 40px 34px; }}

  .masthead {{ text-align: center; padding-bottom: 26px; border-bottom: 1px solid {C['rule']}; }}
  .masthead h1 {{
    font-family: {serif}; font-weight: 700; font-size: 54px; line-height: 1.06;
    letter-spacing: -.02em;
  }}
  .masthead .tagline {{
    margin-top: 8px; font-size: 15px; font-weight: 600; letter-spacing: .2em;
    text-transform: uppercase; color: {C['ink_faint']};
  }}
  .masthead .date {{ margin-top: 18px; font-size: 21px; font-weight: 700; }}
  .masthead .window {{ margin-top: 3px; font-size: 16px; color: {C['ink_soft']}; }}

  .story {{
    background: {C['card']}; border-radius: 18px; padding: 30px 30px 26px;
    margin-top: 24px; box-shadow: 0 12px 30px -18px rgba(16,22,25,.24);
  }}
  .top {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
  .rank {{ font-family: {serif}; font-weight: 700; font-size: 40px; line-height: 1; }}
  .chip {{
    font-size: 14px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
    padding: 5px 12px; border-radius: 6px;
  }}
  .chip.region {{ color: {C['ink_faint']}; background: transparent; border: 1px solid {C['rule']}; }}

  .story h2 {{
    font-family: {serif}; font-weight: 600; font-size: 31px; line-height: 1.26;
    letter-spacing: -.015em; margin-bottom: 12px;
  }}
  .story .hook {{ font-size: 19px; line-height: 1.68; color: {C['ink_soft']}; }}

  .talk {{ margin-top: 22px; padding-top: 20px; border-top: 1px solid {C['rule_soft']}; }}
  .talk-label {{
    font-size: 13px; font-weight: 700; letter-spacing: .13em;
    text-transform: uppercase; margin-bottom: 12px;
  }}
  .talk ul {{ list-style: none; display: flex; flex-direction: column; gap: 11px; }}
  .talk li {{ display: flex; gap: 11px; font-size: 17.5px; line-height: 1.55; }}
  .qn {{ font-family: {serif}; font-weight: 700; font-size: 17px; flex: none; }}

  /* Centred and large on purpose: WeChat's "identify QR in image" has to find
     this inside a very tall picture, so the symbol gets real estate. */
  .qr {{
    margin-top: 30px; background: {C['chrome']}; border-radius: 18px;
    padding: 34px 30px 30px; text-align: center;
  }}
  .qr h3 {{ font-size: 25px; font-weight: 700; color: #fff; line-height: 1.3; }}
  .qr .panel {{
    background: #fff; border-radius: 14px; padding: 16px;
    display: inline-block; margin: 18px 0 16px; line-height: 0;
  }}
  .qr .panel svg {{ display: block; width: 248px; height: 248px; }}
  .qr p {{
    font-size: 15.5px; line-height: 1.65; color: #b9c6cc;
    max-width: 460px; margin: 0 auto;
  }}

  .foot {{
    margin-top: 22px; text-align: center; font-size: 14px; color: {C['ink_faint']};
  }}
</style></head>
<body><div class="sheet">
  <header class="masthead">
    <h1>{e(t('title', lang))}</h1>
    <p class="tagline">{e(t('tagline', lang))}</p>
    <p class="date">{pretty}</p>
    <p class="window">{window}</p>
  </header>
  {''.join(story_block(s, lang) for s in stories)}
  <div class="qr">
    <h3>{e(t('scan', lang))}</h3>
    <div class="panel">{qr_svg(target)}</div>
    <p>{e(t('scan_sub', lang))}</p>
  </div>
  <p class="foot">{e(t('footer', lang))}</p>
</div></body></html>"""


# --------------------------------------------------------------------------- render

def render_png(html_text: str, out_path: Path, keep_html: bool) -> tuple:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "playwright is not installed. Run:\n"
            "  pip install playwright && playwright install chromium"
        )

    html_path = out_path.with_suffix(".html")
    html_path.write_text(html_text, encoding="utf-8")

    executable = os.environ.get("CHROMIUM_PATH")
    launch = {"executable_path": executable} if executable else {}

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        page = browser.new_page(
            viewport={"width": WIDTH, "height": 1200}, device_scale_factor=SCALE
        )
        page.goto(html_path.as_uri())
        # Wait for the webfonts so the image is not rendered mid-swap.
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts && document.fonts.ready")
        page.wait_for_timeout(300)
        height = page.evaluate("document.body.scrollHeight")
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()

    if not keep_html:
        html_path.unlink()
    return WIDTH * SCALE, height * SCALE


def verify_qr(png_path: Path, expected: str) -> str:
    """Decode the QR back out of the finished PNG.

    A broken QR is invisible in review — the poster still looks perfect — and it
    would ship every day until someone tried to scan it. Decoding from the full
    image (not a crop) also approximates what WeChat's "identify QR in image"
    has to do, so a pass here means the symbol is findable at this size.
    """
    try:
        import cv2
    except ImportError:
        return "skipped (opencv not installed)"

    image = cv2.imread(str(png_path))
    if image is None:
        raise SystemExit(f"Could not read back {png_path}")
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    if decoded != expected:
        raise SystemExit(
            f"QR check FAILED for {png_path.name}\n"
            f"  expected: {expected}\n"
            f"  decoded:  {decoded or '(nothing found)'}"
        )
    return "verified"


def main() -> None:
    ap = argparse.ArgumentParser(description="Render an edition as a WeChat long image.")
    ap.add_argument("--date", help="Edition date, YYYY-MM-DD. Defaults to the newest.")
    ap.add_argument("--lang", choices=["en", "zh"], default="zh")
    ap.add_argument("--both", action="store_true", help="Render both languages.")
    ap.add_argument("--out-dir", default=str(POSTER_DIR))
    ap.add_argument("--keep-html", action="store_true", help="Keep the intermediate HTML.")
    args = ap.parse_args()

    if args.date:
        path = EDITIONS_DIR / f"{args.date}.json"
        if not path.exists():
            raise SystemExit(f"No edition for {args.date}.")
    else:
        available = sorted(EDITIONS_DIR.glob("*.json"))
        if not available:
            raise SystemExit("No editions to render.")
        path = available[-1]

    edition = json.loads(path.read_text(encoding="utf-8"))
    site_url = os.environ.get("SITE_URL", DEFAULT_SITE_URL)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    target = f"{site_url.rstrip('/')}/editions/{edition['date']}.html"

    for lang in (["zh", "en"] if args.both else [args.lang]):
        out = out_dir / f"{edition['date']}-{lang}.png"
        w, h = render_png(build_html(edition, lang, site_url), out, args.keep_html)
        size_kb = out.stat().st_size / 1024
        ratio = h / w
        qr_state = verify_qr(out, target)
        print(f"{out.relative_to(ROOT)} — {w}×{h}px, {size_kb:.0f} KB, "
              f"ratio 1:{ratio:.1f}, QR {qr_state}")
        # WeChat crops very tall images hard in the feed thumbnail.
        if ratio > 6:
            print("  warning: taller than 1:6, the feed preview will crop a lot",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
