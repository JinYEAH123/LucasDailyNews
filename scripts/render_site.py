#!/usr/bin/env python3
"""Render the Daily News for Kids site from data/editions/*.json into docs/.

Standard library only. Run after every generation:

    python3 scripts/render_site.py
    python3 scripts/render_site.py --single out.html   # one self-contained page

Beat colours, labels, languages and the family's name all come from
config.toml via appconfig, so the whole look follows the settings.
"""

from __future__ import annotations

import argparse
import html
import json
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
    "archive_intro": {
        "en": "Newest first.", "zh": "从新到旧排列。",
    },
    "archive_first": {
        "en": "This is the first edition. From tomorrow, every past day collects here.",
        "zh": "这是第一期。从明天起，每一天的往期都会收在这里。",
    },
    "empty": {
        "en": "No editions yet. The first one arrives at the time you set.",
        "zh": "还没有内容。第一期会在你设定的时间发布。",
    },
    "built": {"en": "Built", "zh": "生成于"},
    "theme": {"en": "Light / Dark", "zh": "浅色 / 深色"},
    "poster": {"en": "Share image", "zh": "转发长图"},
    "made_for": {"en": "Made for", "zh": "为"},
    "made_for_suffix": {"en": "", "zh": " 而做"},
    "check_source": {
        "en": "Links open the original reporting — always check the source.",
        "zh": "链接会打开原始报道——请随时核对来源。",
    },
    "setup": {"en": "Make your own", "zh": "做一份自己的"},
    "settings": {"en": "Settings", "zh": "设置"},
    "no_match": {
        "en": "Nothing today matches your filters. Open settings and widen them.",
        "zh": "今天没有符合你筛选条件的新闻。打开设置放宽一些。",
    },
}

WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
}

MONTHS_EN = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]


# --------------------------------------------------------------------------- helpers

def e(text: object) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def bilingual(value: object, cls: str = "") -> str:
    """Render a per-language dict as one span per configured language."""
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
        body = "".join(f"<p>{e(p)}</p>" for p in paras)
        out.append(f'<div class="l-{lang}">{body}</div>')
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
    """Only http(s) links pass; anything else renders inert."""
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


def pretty_timestamp(iso: str) -> dict:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return {"en": iso, "zh": iso}
    return {
        "en": f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year} at {d.strftime('%-I:%M %p')}",
        "zh": f"{d.year}年{d.month}月{d.day}日 {d.strftime('%H:%M')}",
    }


def beat_css() -> str:
    """Every beat's accent in both themes, plus the per-card override.

    Generated rather than hand-written so adding a beat to the catalogue is a
    single-file change and can never drift from what the pages actually use.
    """
    light = "".join(
        f"  --{k}: {v['light'][0]}; --{k}-tint: {v['light'][1]};\n"
        for k, v in appconfig.CATEGORIES.items()
    )
    dark = "".join(
        f"    --{k}: {v['dark'][0]}; --{k}-tint: {v['dark'][1]};\n"
        for k, v in appconfig.CATEGORIES.items()
    )
    dark_stamped = "".join(
        f"  --{k}: {v['dark'][0]}; --{k}-tint: {v['dark'][1]};\n"
        for k, v in appconfig.CATEGORIES.items()
    )
    cards = "".join(
        f".story.{k} {{ --accent: var(--{k}); --accent-tint: var(--{k}-tint); }}\n"
        f".archive-item .heads li.{k}::before {{ background: var(--{k}); }}\n"
        for k in appconfig.CATEGORIES
    )
    return (
        f":root {{\n{light}}}\n"
        f"@media (prefers-color-scheme: dark) {{\n"
        f'  :root:not([data-theme="light"]) {{\n{dark}  }}\n}}\n'
        f':root[data-theme="dark"] {{\n{dark_stamped}}}\n'
        f"{cards}"
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
        rows.append(
            f"<li>{title_html}{pub_html}"
            f'<p class="r-sum">{bilingual(item.get("summary", ""))}</p></li>'
        )
    return (
        f"<details><summary>{label(key)}</summary>"
        f'<div class="details-body"><ul class="reads">{"".join(rows)}</ul></div></details>'
    )


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
            f'<p class="r-sum">{bilingual(v.get("summary", ""))}</p></li>'
        )
    if not rows:
        return ""
    return (
        f"<details><summary>{label('watch')}</summary>"
        f'<div class="details-body"><ul class="reads">{"".join(rows)}</ul></div></details>'
    )


def render_words(words: list) -> str:
    if not words:
        return ""
    rows = "".join(
        f"<li><b>{bilingual(w.get('term', ''))}</b> — {bilingual(w.get('def', ''))}</li>"
        for w in words
    )
    return (
        f"<details><summary>{label('words')}</summary>"
        f'<div class="details-body"><ul class="words">{rows}</ul></div></details>'
    )


def render_side(side: dict) -> str:
    return (
        f'<div class="side"><p class="side-label">{bilingual(side.get("label", ""))}</p>'
        f'{bilingual_list(side.get("points"), "side-points")}</div>'
    )


def render_talk(questions: object) -> str:
    """Open by default; the two-sided hints stay folded underneath.

    They should try an answer before they see anyone else's, so opening a hint
    gives them material, never a verdict.
    """
    if isinstance(questions, dict):  # editions from before hints existed
        body = bilingual_list(questions, "questions")
        return (
            f"<details open><summary>{label('talk')}</summary>"
            f'<div class="details-body">{body}</div></details>' if body else ""
        )
    if not questions:
        return ""

    items = []
    for item in questions:
        sides = item.get("sides") or []
        hint = ""
        if sides:
            hint = (
                f'<details class="hint"><summary>{label("talk_hint")}</summary>'
                f'<div class="details-body sides">'
                f'{"".join(render_side(s) for s in sides)}</div></details>'
            )
        items.append(f'<li><p class="q">{bilingual(item.get("question", ""))}</p>{hint}</li>')

    return (
        f"<details open><summary>{label('talk')}</summary>"
        f'<div class="details-body">'
        f'<p class="talk-intro">{label("talk_intro")}</p>'
        f'<ol class="debate">{"".join(items)}</ol>'
        f"</div></details>"
    )


def render_story(story: dict) -> str:
    cat = story.get("category", "")
    region = story.get("region", "GLOBAL")

    why = ""
    if story.get("why_it_matters"):
        why = (f'<div class="why"><span class="label">{label("why")}</span>'
               f'{bilingual(story["why_it_matters"])}</div>')

    source = ""
    src = story.get("source") or {}
    src_url = safe_url(src.get("url"))
    if src_url:
        source = (
            f'<p class="source-line">{label("source")}: '
            f'<a href="{src_url}" target="_blank" rel="noopener noreferrer">'
            f'{e(src.get("title", src.get("publisher", "link")))}</a>'
            f'{" — " + e(src["publisher"]) if src.get("publisher") else ""}</p>'
        )

    full_story = ""
    if story.get("story"):
        full_story = (
            f"<details><summary>{label('read_more')}</summary>"
            f'<div class="details-body story-body">{bilingual_paragraphs(story["story"])}</div>'
            f"</details>"
        )

    return f"""<article class="story {e(cat)}" data-beat="{e(cat)}" data-region="{e(region)}">
  <div class="story-top">
    <span class="rank">{e(story.get('rank', ''))}</span>
    <span class="chip">{cat_label(cat)}</span>
    <span class="chip region">{region_label(region)}</span>
  </div>
  <h2>{bilingual(story.get('headline', ''))}</h2>
  <p class="hook">{bilingual(story.get('hook', ''))}</p>
  {why}
  {full_story}
  {render_words(story.get('word_bank') or [])}
  {render_reads(story.get('background') or [], 'background')}
  {render_reads(story.get('further') or [], 'further')}
  {render_videos(story.get('videos') or [])}
  {render_talk(story.get('talk_about_it'))}
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


def description() -> str:
    return CFG.slogan(CFG.primary_language)


def settings_dialog(depth: int) -> str:
    import setup_page
    return setup_page.render_modal(depth)


def page(title: str, body: str, depth: int = 0) -> str:
    prefix = "../" * depth
    return f"""<!doctype html>
<html lang="{LANGS[0]}" data-lang="{LANGS[0]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description())}">
{FONTS}
<link rel="stylesheet" href="{prefix}assets/styles.css">
<style>{beat_css()}</style>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22><text y=%2214%22 font-size=%2214%22>📰</text></svg>">
</head>
<body>
{gear_button()}
<div class="wrap">
{body}
</div>
{settings_dialog(depth)}
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def lang_buttons() -> str:
    """Only offered when more than one language is configured."""
    if len(LANGS) < 2:
        return ""
    return "".join(
        f'<button type="button" data-lang-set="{l}" '
        f'aria-pressed="{"true" if i == 0 else "false"}">{appconfig.LANGUAGES[l]}</button>'
        for i, l in enumerate(LANGS)
    )


def masthead(date_str, window_label, depth, is_archive, show_nav=True, poster=None) -> str:
    prefix = "../" * depth
    home = f"{prefix}index.html"
    archive = f"{prefix}archive.html"

    dateline = ""
    if date_str:
        dateline = (
            f'<p class="dateline"><strong>{bilingual(pretty_date(date_str))}</strong>'
            + (f"{bilingual(window_label)}" if window_label else "") + "</p>"
        )

    nav = ""
    if show_nav:
        nav = (f'<a class="btn" href="{home}">{label("today")}</a>' if is_archive
               else f'<a class="btn" href="{archive}">{label("archive")}</a>')
    if poster:
        nav += f'<a class="btn" href="{poster}" target="_blank">{label("poster")}</a>'

    title_html = bilingual(appconfig.APP_NAME)
    heading = f'<a href="{home}">{title_html}</a>' if show_nav else title_html

    for_line = ""
    if CFG.child_name:
        for_line = (
            f'<p class="for-line">{label("made_for")} '
            f'<strong>{e(CFG.child_name)}</strong>{label("made_for_suffix")}'
            f' · {CFG.age}</p>'
        )

    return f"""<header class="masthead">
  <h1>{heading}</h1>
  <p class="tagline">{bilingual(appconfig.SLOGAN)}</p>
  {for_line}
  {dateline}
  <div class="controls">
    {lang_buttons()}
    <button type="button" data-theme-toggle>{label("theme")}</button>
    {nav}
  </div>
</header>"""


def gear_button() -> str:
    """Fixed top-right. Opens the same dialog the first visit shows."""
    return (
        '<button type="button" class="gear" data-open-settings '
        f'aria-label="{LABELS["settings"]["en"]}" title="{LABELS["settings"]["en"]}">'
        '<svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true" fill="none" '
        'stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 '
        '1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 '
        '19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 '
        '.33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 '
        '0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 '
        '0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 '
        '2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 '
        '1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></button>'
    )


def no_match_notice() -> str:
    """Shown when a visitor's filters hide every story on the page."""
    return f'<p class="empty no-match" hidden>{label("no_match")}</p>'


def footer(edition: dict | None, depth: int = 0) -> str:
    built = ""
    if edition and edition.get("generated_at"):
        built = (f'{bilingual(LABELS["built"])}: '
                 f'{bilingual(pretty_timestamp(edition["generated_at"]))} · ')
    setup = f'<a href="{"../" * depth}setup.html">{label("setup")}</a>'
    return (
        f'<footer class="foot">{built}{label("check_source")}<br>{setup}</footer>'
    )


def render_edition_page(edition: dict, depth: int) -> str:
    stories = sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99))
    date_str = edition.get("date", "")
    poster = None
    if (OUT / "posters" / f"{date_str}-{LANGS[0]}.png").exists():
        poster = f'{"../" * depth}posters/{date_str}-{LANGS[0]}.png'
    body = (
        masthead(date_str, (edition.get("window") or {}).get("label"), depth, False,
                 poster=poster)
        + "\n".join(render_story(s) for s in stories)
        + no_match_notice()
        + footer(edition, depth)
    )
    return page(f"{appconfig.APP_NAME['en']} — {date_str}", body, depth)


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
                f'<li class="{e(s.get("category", ""))}">{bilingual(s.get("headline", ""))}</li>'
                for s in sorted(ed.get("stories", []), key=lambda s: s.get("rank", 99))
            )
            rows.append(
                f'<li class="archive-item">'
                f'<a class="date" href="editions/{e(ed["date"])}.html">'
                f'{bilingual(pretty_date(ed["date"]))}</a>'
                f'<ul class="heads">{heads}</ul></li>'
            )
        items = f'<ul class="archive-list">{"".join(rows)}</ul>'

    body = (masthead(None, None, 0, True)
            + f'<h2 class="page-head">{label("archive_title")}</h2>'
            + f'<p class="hook">{label("archive_intro")}</p>' + items + footer(None))
    return page(f"{appconfig.APP_NAME['en']} — Archive", body, 0)


def render_single_page(editions: list) -> str:
    """One self-contained page: today, then every past edition collapsed."""
    css = (ASSETS_SRC / "styles.css").read_text(encoding="utf-8")
    js = (ASSETS_SRC / "app.js").read_text(encoding="utf-8")

    if not editions:
        content = f'<p class="empty">{label("empty")}</p>'
        head = masthead(None, None, 0, False, show_nav=False)
    else:
        latest = editions[0]
        head = masthead(latest.get("date"), (latest.get("window") or {}).get("label"),
                        0, False, show_nav=False)
        content = "\n".join(
            render_story(s)
            for s in sorted(latest.get("stories", []), key=lambda s: s.get("rank", 99))
        )

    blocks = []
    for ed in editions[1:]:
        body = "\n".join(
            render_story(s)
            for s in sorted(ed.get("stories", []), key=lambda s: s.get("rank", 99))
        )
        blocks.append(
            f"<details><summary>{bilingual(pretty_date(ed['date']))}</summary>"
            f'<div class="details-body">{body}</div></details>'
        )
    past = (
        f'<h2 class="page-head">{label("archive_title")}</h2>'
        f'<p class="talk-intro">{label("archive_intro")}</p>'
        + ("".join(blocks) if blocks else f'<p class="empty">{label("archive_first")}</p>')
    )

    import setup_page
    # The standalone build has no setup.html to link to, so the dialog's
    # publishing section points at the repository instead.
    dialog = setup_page.render_modal(0).replace(
        'href="setup.html"',
        'href="https://github.com/JinYEAH123/LucasDailyNews" target="_blank" rel="noopener"')

    return f"""<title>{e(appconfig.APP_NAME['en'])}</title>
<meta name="description" content="{e(description())}">
{FONTS}
<style>
{css}
{beat_css()}
</style>
{gear_button()}
<div class="wrap">
{head}
{content}
{no_match_notice()}
{past}
{footer(editions[0] if editions else None)}
</div>
{dialog}
<script>
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
        single_path = Path(args.single)
        single_path.parent.mkdir(parents=True, exist_ok=True)
        single_path.write_text(render_single_page(editions), encoding="utf-8")
        print(f"Wrote self-contained page to {single_path}")

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
        body = masthead(None, None, 0, False) + f'<p class="empty">{label("empty")}</p>' + footer(None)
        (OUT / "index.html").write_text(page(appconfig.APP_NAME["en"], body, 0), encoding="utf-8")

    (OUT / "archive.html").write_text(render_archive_page(editions), encoding="utf-8")

    import setup_page
    (OUT / "setup.html").write_text(setup_page.render(), encoding="utf-8")

    (OUT / "index.json").write_text(
        json.dumps({
            "app": appconfig.APP_NAME["en"],
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "settings": {"count": CFG.count, "age": CFG.age,
                         "categories": CFG.categories, "regions": CFG.regions,
                         "timezone": CFG.timezone, "hour": CFG.hour},
            "editions": [
                {"date": ed["date"], "url": f"editions/{ed['date']}.html",
                 "headlines": [(s.get("headline") or {}).get(LANGS[0], "")
                               for s in sorted(ed.get("stories", []),
                                               key=lambda s: s.get("rank", 99))]}
                for ed in editions
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Rendered {len(editions)} edition(s) into {OUT}")
    if editions:
        print(f"Latest: {editions[0]['date']}")


if __name__ == "__main__":
    main()
