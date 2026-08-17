#!/usr/bin/env python3
"""Render the Lucas Daily News static site from data/editions/*.json into docs/.

Standard library only. Run after every generation:

    python3 scripts/render_site.py

The output in docs/ is what GitHub Pages serves.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"
ASSETS_SRC = Path(__file__).resolve().parent / "assets"
OUT = ROOT / "docs"

SITE_TITLE = {"en": "Lucas Daily News", "zh": "Lucas 每日新闻"}
TAGLINE = {"en": "Three stories that mattered today", "zh": "今天值得知道的三条新闻"}

CATEGORIES = {
    "politics": {"en": "Politics", "zh": "政治"},
    "society": {"en": "Society", "zh": "社会"},
    "business": {"en": "Business", "zh": "财经"},
    "tech": {"en": "Tech", "zh": "科技"},
}

REGIONS = {
    "US": {"en": "United States", "zh": "美国"},
    "CN": {"en": "China", "zh": "中国"},
    "GLOBAL": {"en": "Global", "zh": "全球"},
}

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
        "en": "Newest first. Every edition covers the 24 hours ending at 5:00 PM Vancouver time.",
        "zh": "从新到旧排列。每一期覆盖截至温哥华时间下午5点的24小时。",
    },
    "archive_first": {
        "en": "This is the first edition. From tomorrow, every past day collects here.",
        "zh": "这是第一期。从明天起，每一天的往期都会收在这里。",
    },
    "empty": {
        "en": "No editions yet. The first one arrives at 5:00 PM Vancouver time.",
        "zh": "还没有内容。第一期将在温哥华时间下午5点发布。",
    },
    "built": {"en": "Built", "zh": "生成于"},
    "theme": {"en": "Light / Dark", "zh": "浅色 / 深色"},
}

WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
}

MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# --------------------------------------------------------------------------- helpers

def e(text: object) -> str:
    """Escape untrusted text for HTML body context."""
    return html.escape(str(text if text is not None else ""), quote=True)


def bilingual(value: object, cls: str = "") -> str:
    """Render a {'en':..., 'zh':...} pair as two spans the toggle switches between.

    A plain string is treated as language-neutral and shown in both.
    """
    extra = f" {cls}" if cls else ""
    if isinstance(value, dict):
        return (
            f'<span class="l-en{extra}">{e(value.get("en", ""))}</span>'
            f'<span class="l-zh{extra}">{e(value.get("zh", value.get("en", "")))}</span>'
        )
    return f'<span class="{cls}">{e(value)}</span>' if cls else e(value)


def bilingual_paragraphs(value: object) -> str:
    """Render {'en': [...], 'zh': [...]} (or plain strings) as paragraph blocks."""
    if not isinstance(value, dict):
        return f"<p>{e(value)}</p>"
    out = []
    for lang in ("en", "zh"):
        paras = value.get(lang) or value.get("en") or []
        if isinstance(paras, str):
            paras = [paras]
        body = "".join(f"<p>{e(p)}</p>" for p in paras)
        out.append(f'<div class="l-{lang}">{body}</div>')
    return "".join(out)


def bilingual_list(value: object, css_class: str) -> str:
    """Render {'en': [...], 'zh': [...]} as a pair of <ul>s."""
    if not isinstance(value, dict):
        return ""
    out = []
    for lang in ("en", "zh"):
        items = value.get(lang) or value.get("en") or []
        if not items:
            continue
        lis = "".join(f"<li>{e(i)}</li>" for i in items)
        out.append(f'<ul class="{css_class} l-{lang}">{lis}</ul>')
    return "".join(out)


def label(key: str) -> str:
    return bilingual(LABELS[key])


def safe_url(url: object) -> str:
    """Only allow http(s) links through; anything else becomes an inert anchor."""
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


# --------------------------------------------------------------------------- sections

def render_reads(items: list, key: str) -> str:
    """Background / further-reading lists: title + summary + link."""
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
            if url
            else f'<span class="r-title">{title}</span>'
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
    if not videos:
        return ""
    rows = []
    for v in videos:
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
    rows = []
    for w in words:
        rows.append(
            f"<li><b>{bilingual(w.get('term', ''))}</b> — {bilingual(w.get('def', ''))}</li>"
        )
    return (
        f"<details><summary>{label('words')}</summary>"
        f'<div class="details-body"><ul class="words">{"".join(rows)}</ul></div></details>'
    )


def render_side(side: dict) -> str:
    points = bilingual_list(side.get("points"), "side-points")
    return (
        f'<div class="side"><p class="side-label">{bilingual(side.get("label", ""))}</p>'
        f"{points}</div>"
    )


def render_talk(questions: object) -> str:
    """The independent-thinking exercise: open by default, hints folded underneath.

    Lucas should try an answer before he sees anyone else's. The hints argue both
    sides deliberately, so opening them gives him material, not a verdict.
    """
    # Older editions stored a plain {'en': [...], 'zh': [...]} list of questions.
    if isinstance(questions, dict):
        body = bilingual_list(questions, "questions")
        if not body:
            return ""
        return (
            f"<details open><summary>{label('talk')}</summary>"
            f'<div class="details-body">{body}</div></details>'
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
        items.append(
            f'<li><p class="q">{bilingual(item.get("question", ""))}</p>{hint}</li>'
        )

    return (
        f"<details open><summary>{label('talk')}</summary>"
        f'<div class="details-body">'
        f'<p class="talk-intro">{label("talk_intro")}</p>'
        f'<ol class="debate">{"".join(items)}</ol>'
        f"</div></details>"
    )


def render_story(story: dict) -> str:
    cat = story.get("category", "politics")
    cat_label = CATEGORIES.get(cat, CATEGORIES["politics"])
    region = REGIONS.get(story.get("region", "GLOBAL"), REGIONS["GLOBAL"])

    why = ""
    if story.get("why_it_matters"):
        why = (
            f'<div class="why"><span class="label">{label("why")}</span>'
            f'{bilingual(story["why_it_matters"])}</div>'
        )

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

    return f"""<article class="story {e(cat)}">
  <div class="story-top">
    <span class="rank">{e(story.get('rank', ''))}</span>
    <span class="chip">{bilingual(cat_label)}</span>
    <span class="chip region">{bilingual(region)}</span>
  </div>
  <h2>{bilingual(story.get('headline', ''))}</h2>
  <p class="hook">{bilingual(story.get('hook', ''))}</p>
  {why}
  {full_story}
  {render_words(story.get('word_bank') or [])}
  {render_background_and_further(story)}
  {render_videos(story.get('videos') or [])}
  {render_talk(story.get('talk_about_it'))}
  {source}
</article>"""


def render_background_and_further(story: dict) -> str:
    return render_reads(story.get("background") or [], "background") + render_reads(
        story.get("further") or [], "further"
    )


# --------------------------------------------------------------------------- pages

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Fraunces:opsz,wght@9..144,600;9..144,700&"
    "family=Public+Sans:wght@400;500;600;700&"
    'family=Noto+Sans+SC:wght@400;500;700&display=swap">'
)

DESCRIPTION = "Three stories that mattered today, written for a 12-year-old reader in Vancouver."


def page(title: str, body: str, depth: int = 0) -> str:
    prefix = "../" * depth
    return f"""<!doctype html>
<html lang="en" data-lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(DESCRIPTION)}">
{FONTS}
<link rel="stylesheet" href="{prefix}assets/styles.css">
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


def masthead(
    date_str: str | None,
    window_label: object,
    depth: int,
    is_archive: bool,
    show_nav: bool = True,
) -> str:
    prefix = "../" * depth
    home = f"{prefix}index.html"
    archive = f"{prefix}archive.html"

    dateline = ""
    if date_str:
        pd = pretty_date(date_str)
        dateline = (
            f'<p class="dateline"><strong>{bilingual(pd)}</strong>'
            + (f"{bilingual(window_label)}" if window_label else "")
            + "</p>"
        )

    nav = ""
    if show_nav:
        nav = (
            f'<a class="btn" href="{home}">{label("today")}</a>'
            if is_archive
            else f'<a class="btn" href="{archive}">{label("archive")}</a>'
        )

    title_html = bilingual(SITE_TITLE)
    heading = f'<a href="{home}">{title_html}</a>' if show_nav else title_html

    return f"""<header class="masthead">
  <h1>{heading}</h1>
  <p class="tagline">{bilingual(TAGLINE)}</p>
  {dateline}
  <div class="controls">
    <button type="button" data-lang-set="en" aria-pressed="true">English</button>
    <button type="button" data-lang-set="zh" aria-pressed="false">中文</button>
    <button type="button" data-theme-toggle>{label("theme")}</button>
    {nav}
  </div>
</header>"""


def pretty_timestamp(iso: str) -> dict:
    """Format an ISO timestamp for the footer; fall back to the raw string."""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return {"en": iso, "zh": iso}
    return {
        "en": f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year} at {d.strftime('%-I:%M %p')} PT",
        "zh": f"{d.year}年{d.month}月{d.day}日 {d.strftime('%H:%M')}（温哥华）",
    }


def footer(edition: dict | None) -> str:
    built = ""
    if edition and edition.get("generated_at"):
        stamp = bilingual(pretty_timestamp(edition["generated_at"]))
        built = f'{bilingual(LABELS["built"])}: {stamp} · '
    return (
        f'<footer class="foot">{built}'
        f'<span class="l-en">Made for Lucas. Links open the original reporting — '
        f"always check the source.</span>"
        f'<span class="l-zh">为 Lucas 而做。链接会打开原始报道——请随时核对来源。</span></footer>'
    )


def render_edition_page(edition: dict, depth: int) -> str:
    stories = sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99))
    body = (
        masthead(edition.get("date"), (edition.get("window") or {}).get("label"), depth, False)
        + "\n".join(render_story(s) for s in stories)
        + footer(edition)
    )
    title = f"{SITE_TITLE['en']} — {edition.get('date', '')}"
    return page(title, body, depth)


def render_archive_page(editions: list) -> str:
    if not editions:
        items = f'<p class="empty">{label("empty")}</p>'
    else:
        rows = []
        current_year = None
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

    body = (
        masthead(None, None, 0, True)
        + f'<h2 class="page-head">{label("archive_title")}</h2>'
        + f'<p class="hook">{label("archive_intro")}</p>'
        + items
        + footer(None)
    )
    return page(f"{SITE_TITLE['en']} — Archive", body, 0)


def render_single_page(editions: list) -> str:
    """One self-contained page: today's edition, then every past one collapsed.

    Everything is inlined, so this file can be published or emailed on its own.
    """
    css = (ASSETS_SRC / "styles.css").read_text(encoding="utf-8")
    js = (ASSETS_SRC / "app.js").read_text(encoding="utf-8")

    if not editions:
        content = f'<p class="empty">{label("empty")}</p>'
        head = masthead(None, None, 0, False, show_nav=False)
    else:
        latest = editions[0]
        head = masthead(
            latest.get("date"),
            (latest.get("window") or {}).get("label"),
            0,
            False,
            show_nav=False,
        )
        stories = sorted(latest.get("stories", []), key=lambda s: s.get("rank", 99))
        content = "\n".join(render_story(s) for s in stories)

    # The archive always appears, so it is obvious where past days live even on
    # the very first day.
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

    return f"""<title>Lucas Daily News</title>
<meta name="description" content="{e(DESCRIPTION)}">
{FONTS}
<style>
{css}
</style>
<div class="wrap">
{head}
{content}
{past}
{footer(editions[0] if editions else None)}
</div>
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
    parser = argparse.ArgumentParser(description="Render the Lucas Daily News site.")
    parser.add_argument(
        "--single",
        metavar="FILE",
        help="Also write a single self-contained page (inlined CSS/JS) to FILE.",
    )
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

    # Tell GitHub Pages not to run Jekyll over the output.
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    for ed in editions:
        (OUT / "editions" / f"{ed['date']}.html").write_text(
            render_edition_page(ed, depth=1), encoding="utf-8"
        )

    if editions:
        (OUT / "index.html").write_text(
            render_edition_page(editions[0], depth=0), encoding="utf-8"
        )
    else:
        body = masthead(None, None, 0, False) + f'<p class="empty">{label("empty")}</p>' + footer(None)
        (OUT / "index.html").write_text(page(SITE_TITLE["en"], body, 0), encoding="utf-8")

    (OUT / "archive.html").write_text(render_archive_page(editions), encoding="utf-8")

    # A machine-readable index, handy for checking what exists without parsing HTML.
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "editions": [
                    {
                        "date": ed["date"],
                        "url": f"editions/{ed['date']}.html",
                        "headlines": [
                            (s.get("headline") or {}).get("en", "")
                            for s in sorted(
                                ed.get("stories", []), key=lambda s: s.get("rank", 99)
                            )
                        ],
                    }
                    for ed in editions
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Rendered {len(editions)} edition(s) into {OUT}")
    if editions:
        print(f"Latest: {editions[0]['date']}")


if __name__ == "__main__":
    main()
