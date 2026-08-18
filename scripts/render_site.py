#!/usr/bin/env python3
"""Render the Daily News for Kids site from data/editions/*.json into docs/.

Standard library only.

    python3 scripts/render_site.py
    python3 scripts/render_site.py --single out.html   # one self-contained page

Every page carries all three age bands. Switching between them is a CSS class on
the root element, so it is instant and needs no server — which is the whole
reason the bands are generated up front rather than on demand.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import appconfig

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"
ASSETS_SRC = Path(__file__).resolve().parent / "assets"
OUT = ROOT / "docs"

CFG = appconfig.load()
LANGS = CFG.languages
BANDS = list(appconfig.AGE_BANDS)

LABELS = {
    "read_more": {"en": "Read the whole story", "zh": "读完整篇"},
    "why": {"en": "Why this matters", "zh": "为什么重要"},
    "words": {"en": "Words worth knowing", "zh": "值得记住的词"},
    "talk": {"en": "Talk about it at dinner", "zh": "饭桌上聊聊"},
    "talk_intro": {
        "en": "There is no right answer to any of these. Say what you think first — "
              "then open the hints. Both sides are argued as well as they can be, "
              "so the hints won't decide for you. You still have to pick, and say why.",
        "zh": "这几个问题都没有标准答案。先说说你自己怎么想，再点开提示。"
              "提示里两边都尽力讲了各自的道理，所以它不会替你决定。选哪边、为什么选，还是你的事。",
    },
    "talk_hint": {"en": "Stuck? Two ways to argue it", "zh": "想不出来？两方各有说法"},
    "background": {"en": "Background reading", "zh": "背景阅读"},
    "further": {"en": "Go deeper", "zh": "延展阅读"},
    "watch": {"en": "Watch", "zh": "看视频"},
    "source": {"en": "Main source", "zh": "主要来源"},
    "archive": {"en": "Archive", "zh": "往期"},
    "today": {"en": "Today", "zh": "今日"},
    "archive_title": {"en": "Every past edition", "zh": "所有往期"},
    "archive_intro": {"en": "Newest first.", "zh": "从新到旧排列。"},
    "archive_first": {
        "en": "This is the first edition. From tomorrow, every past day collects here.",
        "zh": "这是第一期。从明天起，每一天的往期都会收在这里。",
    },
    "empty": {
        "en": "No editions yet. The first one arrives at the time you set.",
        "zh": "还没有内容。第一期会在你设定的时间发布。",
    },
    "theme": {"en": "Light / Dark", "zh": "浅色 / 深色"},
    "poster": {"en": "Share image", "zh": "转发长图"},
    "band_prompt": {"en": "Written for", "zh": "读给"},
}

CONTACT_EMAIL = "yejingxin@gmail.com"

WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
}

MONTHS_EN = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]


# --------------------------------------------------------------------------- helpers

def e(text: object) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def band_class(key: str) -> str:
    """A CSS-safe class for a band key — '16+' cannot appear in a selector as-is."""
    return "b-" + re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def bilingual(value: object, cls: str = "") -> str:
    extra = f" {cls}" if cls else ""
    if not isinstance(value, dict):
        return f'<span class="{cls}">{e(value)}</span>' if cls else e(value)
    fallback = next((value[k] for k in value if isinstance(value[k], str)), "")
    return "".join(
        f'<span class="l-{lang}{extra}">{e(value.get(lang) or fallback)}</span>'
        for lang in LANGS
    )


def bilingual_paragraphs(value: object) -> str:
    if not isinstance(value, dict):
        return f"<p>{e(value)}</p>"
    out = []
    for lang in LANGS:
        paras = value.get(lang) or next((v for v in value.values() if v), [])
        if isinstance(paras, str):
            paras = [paras]
        out.append(f'<div class="l-{lang}">{"".join(f"<p>{e(p)}</p>" for p in paras)}</div>')
    return "".join(out)


def bilingual_list(value: object, css_class: str) -> str:
    if not isinstance(value, dict):
        return ""
    out = []
    for lang in LANGS:
        items = value.get(lang) or next((v for v in value.values() if v), [])
        if not items:
            continue
        lis = "".join(f"<li>{e(i)}</li>" for i in items)
        out.append(f'<ul class="{css_class} l-{lang}">{lis}</ul>')
    return "".join(out)


def label(key: str) -> str:
    return bilingual(LABELS[key])


def cat_label(key: str) -> str:
    entry = appconfig.CATEGORIES.get(key)
    return bilingual(entry["label"]) if entry else e(key)


def region_label(key: str) -> str:
    entry = appconfig.REGIONS.get(key)
    return bilingual(entry["label"]) if entry else e(key)


def safe_url(url: object) -> str:
    text = str(url or "").strip()
    if text.lower().startswith(("http://", "https://")):
        return html.escape(text, quote=True)
    return ""


def pretty_date(date_str: str) -> dict:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    idx = d.weekday()
    return {
        "en": f"{WEEKDAYS['en'][idx]}, {MONTHS_EN[d.month - 1]} {d.day}, {d.year}",
        "zh": f"{d.year}年{d.month}月{d.day}日 {WEEKDAYS['zh'][idx]}",
    }


def generated_css() -> str:
    """Beat accents and band switching, both derived from the catalogues.

    Generated rather than hand-written so adding a beat or a band is a
    single-file change that cannot drift from what the pages actually use.
    """
    light = "".join(f"  --{k}: {v['light'][0]}; --{k}-tint: {v['light'][1]};\n"
                    for k, v in appconfig.CATEGORIES.items())
    dark = "".join(f"  --{k}: {v['dark'][0]}; --{k}-tint: {v['dark'][1]};\n"
                   for k, v in appconfig.CATEGORIES.items())
    cards = "".join(
        f".story.{k} {{ --accent: var(--{k}); --accent-tint: var(--{k}-tint); }}\n"
        f".archive-item .heads li.{k}::before {{ background: var(--{k}); }}\n"
        for k in appconfig.CATEGORIES
    )
    # One rule per band: when the root is on band X, every other band is hidden.
    hide = "".join(
        f'[data-band="{b}"] .band:not(.{band_class(b)}) {{ display: none; }}\n'
        for b in BANDS
    )
    return (
        f":root {{\n{light}}}\n"
        f'@media (prefers-color-scheme: dark) {{\n  :root:not([data-theme="light"]) {{\n'
        + "".join("  " + l + "\n" for l in dark.strip().splitlines())
        + f"  }}\n}}\n"
        f':root[data-theme="dark"] {{\n{dark}}}\n'
        f"{cards}{hide}"
    )


# --------------------------------------------------------------------------- sections

def render_reads(items: list, key: str) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        url = safe_url(item.get("url"))
        title = bilingual(item.get("title", ""))
        pub = item.get("publisher")
        pub_html = f'<span class="r-pub">{e(pub)}</span>' if pub else ""
        title_html = (
            f'<a class="r-title" href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            if url else f'<span class="r-title">{title}</span>'
        )
        rows.append(f"<li>{title_html}{pub_html}"
                    f'<p class="r-sum">{bilingual(item.get("summary", ""))}</p></li>')
    return (f"<details><summary>{label(key)}</summary>"
            f'<div class="details-body"><ul class="reads">{"".join(rows)}</ul></div></details>')


def render_videos(videos: list) -> str:
    rows = []
    for v in videos or []:
        url = safe_url(v.get("url"))
        if not url:
            continue
        channel = f'<span class="r-pub">{e(v["channel"])}</span>' if v.get("channel") else ""
        rows.append(
            f'<li><a class="video-link" href="{url}" target="_blank" rel="noopener noreferrer">'
            f'{e(v.get("title", "Video"))}</a>{channel}'
            f'<p class="r-sum">{bilingual(v.get("summary", ""))}</p></li>')
    if not rows:
        return ""
    return (f"<details><summary>{label('watch')}</summary>"
            f'<div class="details-body"><ul class="reads">{"".join(rows)}</ul></div></details>')


def render_words(words: list) -> str:
    if not words:
        return ""
    rows = "".join(f"<li><b>{bilingual(w.get('term', ''))}</b> — {bilingual(w.get('def', ''))}</li>"
                   for w in words)
    return (f"<details><summary>{label('words')}</summary>"
            f'<div class="details-body"><ul class="words">{rows}</ul></div></details>')


def render_side(side: dict) -> str:
    return (f'<div class="side"><p class="side-label">{bilingual(side.get("label", ""))}</p>'
            f'{bilingual_list(side.get("points"), "side-points")}</div>')


def render_talk(questions: object) -> str:
    """Open by default; the two-sided hints stay folded underneath, so a child
    tries an answer before meeting anyone else's."""
    if not questions:
        return ""
    items = []
    for item in questions:
        sides = item.get("sides") or []
        hint = ""
        if sides:
            hint = (f'<details class="hint"><summary>{label("talk_hint")}</summary>'
                    f'<div class="details-body sides">'
                    f'{"".join(render_side(s) for s in sides)}</div></details>')
        items.append(f'<li><p class="q">{bilingual(item.get("question", ""))}</p>{hint}</li>')
    return (f"<details open><summary>{label('talk')}</summary>"
            f'<div class="details-body"><p class="talk-intro">{label("talk_intro")}</p>'
            f'<ol class="debate">{"".join(items)}</ol></div></details>')


def render_story(story: dict) -> str:
    cat = story.get("category", "")
    region = story.get("region", "GLOBAL")
    versions = story.get("versions") or {}

    head_blocks, talk_blocks = [], []
    for band in BANDS:
        v = versions.get(band)
        if not v:
            continue
        cls = band_class(band)
        why = ""
        if v.get("why_it_matters"):
            why = (f'<div class="why"><span class="label">{label("why")}</span>'
                   f'{bilingual(v["why_it_matters"])}</div>')
        full = ""
        if v.get("story"):
            full = (f"<details><summary>{label('read_more')}</summary>"
                    f'<div class="details-body story-body">'
                    f'{bilingual_paragraphs(v["story"])}</div></details>')
        head_blocks.append(
            f'<div class="band {cls}">'
            f'<h2>{bilingual(v.get("headline", ""))}</h2>'
            f'<p class="hook">{bilingual(v.get("hook", ""))}</p>'
            f'{why}{full}{render_words(v.get("word_bank") or [])}</div>')
        talk_blocks.append(
            f'<div class="band {cls}">{render_talk(v.get("talk_about_it"))}</div>')

    source = ""
    src = story.get("source") or {}
    src_url = safe_url(src.get("url"))
    if src_url:
        source = (f'<p class="source-line">{label("source")}: '
                  f'<a href="{src_url}" target="_blank" rel="noopener noreferrer">'
                  f'{e(src.get("title", src.get("publisher", "link")))}</a>'
                  f'{" — " + e(src["publisher"]) if src.get("publisher") else ""}</p>')

    return f"""<article class="story {e(cat)}">
  <div class="story-top">
    <span class="rank">{e(story.get('rank', ''))}</span>
    <span class="chip">{cat_label(cat)}</span>
    <span class="chip region">{region_label(region)}</span>
  </div>
  {''.join(head_blocks)}
  {render_reads(story.get('background') or [], 'background')}
  {render_reads(story.get('further') or [], 'further')}
  {render_videos(story.get('videos') or [])}
  {''.join(talk_blocks)}
  {source}
</article>"""


# --------------------------------------------------------------------------- pages

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Fraunces:opsz,wght@9..144,600;9..144,700&"
    "family=Public+Sans:wght@400;500;600;700&"
    'family=Noto+Sans+SC:wght@400;500;700&display=swap">'
)


def page(title: str, body: str, depth: int = 0) -> str:
    prefix = "../" * depth
    return f"""<!doctype html>
<html lang="{LANGS[0]}" data-lang="{LANGS[0]}" data-band="{CFG.band}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(CFG.slogan(LANGS[0]))}">
{FONTS}
<link rel="stylesheet" href="{prefix}assets/styles.css">
<style>{generated_css()}</style>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22><text y=%2214%22 font-size=%2214%22>📰</text></svg>">
</head>
<body>
<div class="wrap">
{body}
</div>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def band_bar() -> str:
    """The one control that changes the writing. It is on the page, not behind a
    menu, because choosing the right reading level is the first thing a parent
    needs to do and the only thing most of them will ever change."""
    buttons = "".join(
        f'<button type="button" data-band-set="{e(b)}" '
        f'aria-pressed="{"true" if b == CFG.band else "false"}">'
        f'{bilingual(appconfig.AGE_BANDS[b]["label"])}</button>'
        for b in BANDS
    )
    return (f'<div class="bandbar"><span class="bandbar-label">{label("band_prompt")}</span>'
            f'<div class="seg">{buttons}</div></div>')


def lang_buttons() -> str:
    if len(LANGS) < 2:
        return ""
    return "".join(
        f'<button type="button" data-lang-set="{l}" '
        f'aria-pressed="{"true" if i == 0 else "false"}">{appconfig.LANGUAGES[l]}</button>'
        for i, l in enumerate(LANGS)
    )


def masthead(date_str, window_label, depth, is_archive, show_nav=True, posters=None) -> str:
    prefix = "../" * depth
    home, archive = f"{prefix}index.html", f"{prefix}archive.html"

    dateline = ""
    if date_str:
        dateline = (f'<p class="dateline"><strong>{bilingual(pretty_date(date_str))}</strong>'
                    + (f"{bilingual(window_label)}" if window_label else "") + "</p>")

    nav = ""
    if show_nav:
        nav = (f'<a class="btn" href="{home}">{label("today")}</a>' if is_archive
               else f'<a class="btn" href="{archive}">{label("archive")}</a>')
    # One link per language rather than one bilingual link: the poster is a
    # different image in each language, so the href has to switch with the page,
    # not just the button's wording.
    for lang in LANGS:
        href = (posters or {}).get(lang)
        if href:
            nav += (f'<a class="btn l-{lang}" href="{href}" target="_blank">'
                    f'{e(LABELS["poster"][lang])}</a>')

    title_html = bilingual(appconfig.APP_NAME)
    heading = f'<a href="{home}">{title_html}</a>' if show_nav else title_html

    return f"""<header class="masthead">
  <h1>{heading}</h1>
  <p class="tagline">{bilingual(appconfig.SLOGAN)}</p>
  {dateline}
  <div class="controls">
    {lang_buttons()}
    <button type="button" data-theme-toggle>{label("theme")}</button>
    {nav}
  </div>
</header>"""


def footer() -> str:
    return (f'<footer class="foot"><p class="contact">'
            f'Contact me: <a href="mailto:{CONTACT_EMAIL}">{e(CONTACT_EMAIL)}</a></p></footer>')


def render_edition_page(edition: dict, depth: int) -> str:
    stories = sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99))
    date_str = edition.get("date", "")
    posters = {
        lang: f'{"../" * depth}posters/{date_str}-{lang}.png'
        for lang in LANGS
        if (OUT / "posters" / f"{date_str}-{lang}.png").exists()
    }
    body = (masthead(date_str, (edition.get("window") or {}).get("label"), depth, False,
                     posters=posters)
            + band_bar()
            + "\n".join(render_story(s) for s in stories)
            + footer())
    return page(f"{appconfig.APP_NAME['en']} — {date_str}", body, depth)


def headline_of(story: dict) -> dict:
    """An archive line needs one headline; use the default band's."""
    versions = story.get("versions") or {}
    v = versions.get(CFG.band) or next(iter(versions.values()), {})
    return v.get("headline", {})


def render_archive_page(editions: list) -> str:
    if not editions:
        items = f'<p class="empty">{label("empty")}</p>'
    else:
        rows, current_year = [], None
        for ed in editions:
            year = ed["date"][:4]
            if year != current_year:
                rows.append(f'<li class="year-head">{e(year)}</li>')
                current_year = year
            heads = "".join(
                f'<li class="{e(s.get("category", ""))}">{bilingual(headline_of(s))}</li>'
                for s in sorted(ed.get("stories", []), key=lambda s: s.get("rank", 99)))
            rows.append(f'<li class="archive-item">'
                        f'<a class="date" href="editions/{e(ed["date"])}.html">'
                        f'{bilingual(pretty_date(ed["date"]))}</a>'
                        f'<ul class="heads">{heads}</ul></li>')
        items = f'<ul class="archive-list">{"".join(rows)}</ul>'

    body = (masthead(None, None, 0, True)
            + f'<h2 class="page-head">{label("archive_title")}</h2>'
            + f'<p class="hook">{label("archive_intro")}</p>' + items + footer())
    return page(f"{appconfig.APP_NAME['en']} — Archive", body, 0)


def render_single_page(editions: list) -> str:
    css = (ASSETS_SRC / "styles.css").read_text(encoding="utf-8")
    js = (ASSETS_SRC / "app.js").read_text(encoding="utf-8")

    if not editions:
        content = f'<p class="empty">{label("empty")}</p>'
        head = masthead(None, None, 0, False, show_nav=False)
    else:
        latest = editions[0]
        head = masthead(latest.get("date"), (latest.get("window") or {}).get("label"),
                        0, False, show_nav=False)
        content = "\n".join(render_story(s) for s in
                            sorted(latest.get("stories", []), key=lambda s: s.get("rank", 99)))

    blocks = []
    for ed in editions[1:]:
        body = "\n".join(render_story(s) for s in
                         sorted(ed.get("stories", []), key=lambda s: s.get("rank", 99)))
        blocks.append(f"<details><summary>{bilingual(pretty_date(ed['date']))}</summary>"
                      f'<div class="details-body">{body}</div></details>')
    past = (f'<h2 class="page-head">{label("archive_title")}</h2>'
            f'<p class="talk-intro">{label("archive_intro")}</p>'
            + ("".join(blocks) if blocks else f'<p class="empty">{label("archive_first")}</p>'))

    # The wrapper supplies <html>, so the band/lang defaults are set by script.
    return f"""<title>{e(appconfig.APP_NAME['en'])}</title>
<meta name="description" content="{e(CFG.slogan(LANGS[0]))}">
{FONTS}
<style>
{css}
{generated_css()}
</style>
<div class="wrap">
{head}
{band_bar()}
{content}
{past}
{footer()}
</div>
<script>
document.documentElement.setAttribute('data-lang', '{LANGS[0]}');
document.documentElement.setAttribute('data-band', '{CFG.band}');
{js}
</script>
"""


# --------------------------------------------------------------------------- main

def load_editions() -> list:
    editions = []
    for path in sorted(EDITIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name} is not valid JSON: {exc}") from exc
        if not data.get("date"):
            raise SystemExit(f"{path.name} is missing a 'date' field")
        editions.append(data)
    editions.sort(key=lambda ed: ed["date"], reverse=True)
    return editions


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the site.")
    parser.add_argument("--single", metavar="FILE",
                        help="Also write a single self-contained page to FILE.")
    args = parser.parse_args()

    editions = load_editions()

    if args.single:
        p = Path(args.single)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_single_page(editions), encoding="utf-8")
        print(f"Wrote self-contained page to {p}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "editions").mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    for name in ("styles.css", "app.js"):
        shutil.copyfile(ASSETS_SRC / name, OUT / "assets" / name)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    for ed in editions:
        (OUT / "editions" / f"{ed['date']}.html").write_text(
            render_edition_page(ed, depth=1), encoding="utf-8")

    if editions:
        (OUT / "index.html").write_text(render_edition_page(editions[0], depth=0),
                                        encoding="utf-8")
    else:
        body = masthead(None, None, 0, False) + f'<p class="empty">{label("empty")}</p>' + footer()
        (OUT / "index.html").write_text(page(appconfig.APP_NAME["en"], body, 0), encoding="utf-8")

    (OUT / "archive.html").write_text(render_archive_page(editions), encoding="utf-8")

    import setup_page
    (OUT / "setup.html").write_text(setup_page.render(), encoding="utf-8")

    (OUT / "index.json").write_text(json.dumps({
        "app": appconfig.APP_NAME["en"],
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bands": BANDS,
        "editions": [{"date": ed["date"], "url": f"editions/{ed['date']}.html"}
                     for ed in editions],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Rendered {len(editions)} edition(s) into {OUT}")


if __name__ == "__main__":
    main()
