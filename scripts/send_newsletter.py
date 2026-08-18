#!/usr/bin/env python3
"""Email one edition of Daily News for Kids to the subscriber list.

Reads data/editions/<date>.json and sends a multipart (plain text + HTML) email
over SMTP. The HTML is built separately from the website's: mail clients do not
support <details>, CSS variables, flexbox, or web fonts, so this renderer uses
tables and inline styles only.

The dinner questions are included, but the two-sided hints deliberately are not
— they stay on the website behind a fold so the child answers before reading
anyone else's arguments. Each story links to its page for them.

Configuration, all through the environment so no address is ever committed:

    SMTP_HOST              e.g. smtp.gmail.com
    SMTP_PORT              465 for implicit TLS, 587 for STARTTLS (default 587)
    SMTP_USER              the account that authenticates
    SMTP_PASSWORD          an app password, never the account password
    SMTP_FROM              From address (defaults to SMTP_USER; Gmail rewrites
                           anything that is not the authenticated account)
    SMTP_FROM_NAME         display name (default "Daily News for Kids")
    NEWSLETTER_RECIPIENTS  comma- or newline-separated. "addr" or "addr:lang",
                           where lang is en or zh. Defaults to the first
                           language in config.toml.
                           e.g. "lucas@x.com:en, mum@x.com:zh"
    SITE_URL               where the site is published, used for the links out

Usage:
    python3 scripts/send_newsletter.py                      # today's edition
    python3 scripts/send_newsletter.py --date 2026-08-17
    python3 scripts/send_newsletter.py --dry-run out.html   # preview, no send
    python3 scripts/send_newsletter.py --to me@x.com --lang zh
    python3 scripts/send_newsletter.py --force              # resend a sent date
"""

from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

import appconfig
import render_site as site

ROOT = Path(__file__).resolve().parent.parent
EDITIONS_DIR = ROOT / "data" / "editions"
SENT_LOG = ROOT / "data" / "sent.json"

CFG = appconfig.load()

# Light palette only. Mail clients apply their own dark-mode transforms and
# there is no reliable way to opt out, so these are chosen to survive inversion.
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

BEAT = appconfig.beat_colors("light")

SERIF = "Georgia,'Iowan Old Style','Times New Roman',serif"
SANS = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
        "Arial,'PingFang SC','Microsoft YaHei',sans-serif")

T = {
    "why": {"en": "Why this matters", "zh": "为什么重要"},
    "words": {"en": "Words worth knowing", "zh": "值得记住的词"},
    "talk": {"en": "Talk about it at dinner", "zh": "饭桌上聊聊"},
    "talk_note": {
        "en": "Try your own answer first. The case for both sides is on the website —",
        "zh": "先说说你自己怎么想。两方各自的说法在网页上——",
    },
    "talk_link": {"en": "see both sides", "zh": "看两方的说法"},
    "background": {"en": "Background reading", "zh": "背景阅读"},
    "further": {"en": "Go deeper", "zh": "延展阅读"},
    "watch": {"en": "Watch", "zh": "看视频"},
    "source": {"en": "Main source", "zh": "主要来源"},
    "read_online": {"en": "Read this online", "zh": "在网页上读"},
    "archive": {"en": "Past editions", "zh": "往期"},
}


def t(key: str, lang: str) -> str:
    return T[key][lang]


def footer_line(lang: str) -> str:
    if lang == "zh":
        return ("本邮件由你自己的新闻仓库发出。要增减收件人，"
                "请修改仓库设置里的 NEWSLETTER_RECIPIENTS。")
    return ("Sent from your own news repository. To add or remove a reader, edit "
            "the NEWSLETTER_RECIPIENTS secret in the repository settings.")


def app_title(lang: str) -> str:
    return appconfig.APP_NAME.get(lang, appconfig.APP_NAME["en"])


def app_slogan(lang: str) -> str:
    return appconfig.SLOGAN.get(lang, appconfig.SLOGAN["en"])


def pick(value: object, lang: str) -> str:
    """Take one language out of a {'en':…, 'zh':…} pair."""
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    return str(value or "")


def pick_list(value: object, lang: str) -> list:
    if isinstance(value, dict):
        items = value.get(lang) or value.get("en") or []
        return [items] if isinstance(items, str) else list(items)
    if isinstance(value, list):
        return value
    return []


def e(text: object) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


# --------------------------------------------------------------------------- html

def link(url: str, text: str, color: str, bold: bool = True) -> str:
    safe = site.safe_url(url)
    weight = "600" if bold else "400"
    if not safe:
        return f'<span style="color:{C["ink"]};font-weight:{weight}">{text}</span>'
    return (
        f'<a href="{safe}" style="color:{color};font-weight:{weight};'
        f'text-decoration:underline">{text}</a>'
    )


def section_label(text: str, color: str) -> str:
    return (
        f'<p style="margin:18px 0 6px;font:700 11px/1.4 {SANS};'
        f'letter-spacing:.1em;text-transform:uppercase;color:{color}">{text}</p>'
    )


def reading_block(items: list, heading: str, accent: str, lang: str) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        title = e(pick(item.get("title"), lang))
        summary = e(pick(item.get("summary"), lang))
        pub = e(item.get("publisher", ""))
        pub_html = (
            f'<span style="color:{C["ink_faint"]};font-size:12px"> — {pub}</span>'
            if pub else ""
        )
        rows.append(
            f'<p style="margin:0 0 10px;font:400 14px/1.55 {SANS};color:{C["ink_soft"]}">'
            f'{link(item.get("url", ""), title, C["ink"])}{pub_html}<br>{summary}</p>'
        )
    return section_label(heading, accent) + "".join(rows)


def story_html(story: dict, lang: str, story_url: str, band: str) -> str:
    v = (story.get("versions") or {}).get(band) or {}
    cat = story.get("category", "politics")
    accent, tint = BEAT.get(cat, BEAT["politics"])
    cat_name = e(appconfig.category_label(cat, lang))
    region = e(appconfig.region_label(story.get("region", "GLOBAL"), lang))

    body = "".join(
        f'<p style="margin:0 0 12px;font:400 15px/1.65 {SANS};color:{C["ink"]}">{e(p)}</p>'
        for p in pick_list(v.get("story"), lang)
    )

    words = ""
    if v.get("word_bank"):
        rows = "".join(
            f'<p style="margin:0 0 8px;font:400 14px/1.55 {SANS};color:{C["ink_soft"]}">'
            f'<b style="color:{C["ink"]}">{e(pick(w.get("term"), lang))}</b> — '
            f'{e(pick(w.get("def"), lang))}</p>'
            for w in v["word_bank"]
        )
        words = section_label(t("words", lang), accent) + rows

    # Questions only. The two-sided hints live behind a fold on the website so
    # the child commits to a view before reading anyone else's arguments.
    talk = ""
    questions = v.get("talk_about_it")
    if isinstance(questions, list) and questions:
        rows = "".join(
            f'<tr><td valign="top" width="20" '
            f'style="font:700 15px/1.5 {SERIF};color:{accent};padding:0 8px 8px 0">{i}</td>'
            f'<td style="font:600 15px/1.5 {SANS};color:{C["ink"]};padding:0 0 8px">'
            f'{e(pick(q.get("question"), lang))}</td></tr>'
            for i, q in enumerate(questions, 1)
        )
        talk = (
            section_label(t("talk", lang), accent)
            + f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
              f'width="100%">{rows}</table>'
            + f'<p style="margin:4px 0 0;font:400 13px/1.55 {SANS};color:{C["ink_faint"]}">'
              f'{t("talk_note", lang)} '
              f'{link(story_url, t("talk_link", lang), accent)}</p>'
        )

    videos = ""
    if story.get("videos"):
        rows = "".join(
            f'<p style="margin:0 0 8px;font:400 14px/1.55 {SANS};color:{C["ink_soft"]}">'
            f'▶ {link(v.get("url", ""), e(v.get("title", "Video")), C["ink"])}<br>'
            f'{e(pick(v.get("summary"), lang))}</p>'
            for v in story["videos"]
            if site.safe_url(v.get("url"))
        )
        if rows:
            videos = section_label(t("watch", lang), accent) + rows

    src = story.get("source") or {}
    source = ""
    if site.safe_url(src.get("url")):
        source = (
            f'<p style="margin:16px 0 0;padding-top:12px;'
            f'border-top:1px solid {C["rule_soft"]};'
            f'font:400 12px/1.5 {SANS};color:{C["ink_faint"]}">'
            f'{t("source", lang)}: '
            f'{link(src["url"], e(src.get("title", "")), C["ink_soft"], bold=False)}'
            f' — {e(src.get("publisher", ""))}</p>'
        )

    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
  style="background:{C['card']};border:1px solid {C['rule_soft']};border-radius:10px;margin:0 0 20px">
  <tr><td style="padding:22px 22px 18px">
    <p style="margin:0 0 8px;font:400 13px/1 {SANS}">
      <span style="font:700 22px/1 {SERIF};color:{accent}">{e(story.get('rank', ''))}</span>
      <span style="display:inline-block;padding:3px 8px;margin-left:8px;border-radius:4px;
        background:{tint};color:{accent};font:700 11px/1.4 {SANS};
        letter-spacing:.1em;text-transform:uppercase">{cat_name}</span>
      <span style="display:inline-block;padding:3px 8px;margin-left:4px;border-radius:4px;
        border:1px solid {C['rule']};color:{C['ink_faint']};font:700 11px/1.4 {SANS};
        letter-spacing:.1em;text-transform:uppercase">{region}</span>
    </p>
    <h2 style="margin:0 0 10px;font:600 22px/1.25 {SERIF};color:{C['ink']}">
      {e(pick(v.get('headline'), lang))}</h2>
    <p style="margin:0 0 14px;font:400 15px/1.6 {SANS};color:{C['ink_soft']}">
      {e(pick(v.get('hook'), lang))}</p>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
      style="background:{tint};border-left:3px solid {accent};border-radius:0 6px 6px 0;margin:0 0 16px">
      <tr><td style="padding:12px 14px">
        <p style="margin:0 0 3px;font:700 11px/1.4 {SANS};letter-spacing:.1em;
          text-transform:uppercase;color:{accent}">{t('why', lang)}</p>
        <p style="margin:0;font:400 14px/1.6 {SANS};color:{C['ink']}">
          {e(pick(v.get('why_it_matters'), lang))}</p>
      </td></tr>
    </table>
    {body}
    {words}
    {talk}
    {reading_block(story.get('background') or [], t('background', lang), accent, lang)}
    {reading_block(story.get('further') or [], t('further', lang), accent, lang)}
    {videos}
    {source}
  </td></tr>
</table>"""


def build_html(edition: dict, lang: str, site_url: str, band: str) -> str:
    date_str = edition["date"]
    pretty = pick(site.pretty_date(date_str), lang)
    window = pick((edition.get("window") or {}).get("label"), lang)
    stories = sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99))

    base = site_url.rstrip("/")
    story_url = f"{base}/editions/{date_str}.html"
    archive_url = f"{base}/archive.html"

    # Shown in the inbox preview line, then hidden in the body.
    preheader = (e(pick((stories[0].get("versions") or {}).get(band, {}).get("hook"), lang))[:160]
                 if stories else "")

    cards = "".join(story_html(s, lang, story_url, band) for s in stories)

    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(app_title(lang))} — {e(pretty)}</title></head>
<body style="margin:0;padding:0;background:{C['paper']}">
<div style="display:none;font-size:1px;color:{C['paper']};max-height:0;overflow:hidden">{preheader}</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
  style="background:{C['paper']}">
  <tr><td align="center" style="padding:24px 12px 40px">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
      style="width:100%;max-width:600px">
      <tr><td align="center" style="padding:0 0 22px;border-bottom:1px solid {C['rule']}">
        <h1 style="margin:0 0 4px;font:700 30px/1.1 {SERIF};color:{C['ink']}">
          {e(app_title(lang))}</h1>
        <p style="margin:0 0 10px;font:600 11px/1.4 {SANS};letter-spacing:.16em;
          text-transform:uppercase;color:{C['ink_faint']}">{e(app_slogan(lang))}</p>
        <p style="margin:0;font:700 14px/1.5 {SANS};color:{C['ink']}">{e(pretty)}</p>
        <p style="margin:0;font:400 13px/1.5 {SANS};color:{C['ink_soft']}">{e(window)}</p>
      </td></tr>
      <tr><td style="padding:22px 0 0">{cards}</td></tr>
      <tr><td align="center" style="padding:8px 0 0;border-top:1px solid {C['rule']}">
        <p style="margin:14px 0 6px;font:400 13px/1.6 {SANS}">
          {link(story_url, e(t('read_online', lang)), C['chrome'])}
          <span style="color:{C['ink_faint']}"> · </span>
          {link(archive_url, e(t('archive', lang)), C['chrome'])}
        </p>
        <p style="margin:0;font:400 12px/1.6 {SANS};color:{C['ink_faint']}">
          {e(footer_line(lang))}</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


# --------------------------------------------------------------------------- text

def build_text(edition: dict, lang: str, site_url: str, band: str) -> str:
    date_str = edition["date"]
    base = site_url.rstrip("/")
    story_url = f"{base}/editions/{date_str}.html"

    out = [
        app_title(lang),
        pick(site.pretty_date(date_str), lang),
        pick((edition.get("window") or {}).get("label"), lang),
        "",
    ]

    for story in sorted(edition.get("stories", []), key=lambda s: s.get("rank", 99)):
        v = (story.get("versions") or {}).get(band) or {}
        cat = appconfig.category_label(story.get("category", ""), lang)
        out += [
            "=" * 60,
            f"{story.get('rank', '')}. [{cat}] {pick(v.get('headline'), lang)}",
            "",
            pick(v.get("hook"), lang),
            "",
            f"{t('why', lang)}: {pick(v.get('why_it_matters'), lang)}",
            "",
        ]
        out += [p + "\n" for p in pick_list(v.get("story"), lang)]

        if v.get("word_bank"):
            out.append(t("words", lang))
            out += [
                f"  - {pick(w.get('term'), lang)}: {pick(w.get('def'), lang)}"
                for w in v["word_bank"]
            ]
            out.append("")

        questions = v.get("talk_about_it")
        if isinstance(questions, list) and questions:
            out.append(t("talk", lang))
            out += [
                f"  {i}. {pick(q.get('question'), lang)}"
                for i, q in enumerate(questions, 1)
            ]
            out += [f"  {t('talk_note', lang)} {story_url}", ""]

        for key, items in (("background", story.get("background")),
                           ("further", story.get("further"))):
            if items:
                out.append(t(key, lang))
                out += [
                    f"  - {pick(i.get('title'), lang)} ({i.get('publisher', '')})\n    {i.get('url', '')}"
                    for i in items
                ]
                out.append("")

        for video in story.get("videos") or []:
            out.append(f"{t('watch', lang)}: {video.get('title', '')} — {video.get('url', '')}")

        src = story.get("source") or {}
        if src.get("url"):
            out += [f"{t('source', lang)}: {src.get('title', '')} — {src['url']}", ""]

    out += ["=" * 60, f"{t('read_online', lang)}: {story_url}", footer_line(lang)]
    return "\n".join(out)


# --------------------------------------------------------------------------- recipients

def parse_recipients(raw: str) -> list:
    """Parse "addr", "addr:lang", "addr:band" or "addr:lang:band" entries.

    Two children of different ages in one household is the case this exists for.
    Parts after the address are matched against the known languages and bands
    rather than being positional, so order does not matter and a stray colon in
    an address cannot silently become a setting.
    """
    known_langs = set(appconfig.LANGUAGES)
    known_bands = set(appconfig.AGE_BANDS)
    recipients = []

    for chunk in raw.replace("\n", ",").split(","):
        entry = chunk.strip()
        if not entry:
            continue
        parts = entry.split(":")
        addr = parts[0].strip()
        lang, band = CFG.primary_language, CFG.band
        unknown = []
        for part in parts[1:]:
            token = part.strip()
            if token.lower() in known_langs:
                lang = token.lower()
            elif token in known_bands:
                band = token
            elif token:
                unknown.append(token)
        if "@" not in addr:
            print(f"  skipping '{entry}' — not an email address", file=sys.stderr)
            continue
        if unknown:
            print(f"  note: ignoring {unknown} on {addr}; "
                  f"expected one of {sorted(known_langs)} or {sorted(known_bands)}",
                  file=sys.stderr)
        recipients.append((addr, lang, band))
    return recipients


def load_sent_log() -> dict:
    if SENT_LOG.exists():
        try:
            return json.loads(SENT_LOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def record_sent(date_str: str, count: int) -> None:
    log = load_sent_log()
    log[date_str] = {
        "sent_at": datetime.now(CFG.tz).isoformat(timespec="seconds"),
        "recipients": count,
    }
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(
        json.dumps(dict(sorted(log.items(), reverse=True)), indent=2) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- send

def send(edition: dict, recipients: list, site_url: str) -> int:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not (host and user and password):
        raise SystemExit("SMTP_HOST, SMTP_USER and SMTP_PASSWORD must all be set.")

    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("SMTP_FROM", user)
    from_name = os.environ.get("SMTP_FROM_NAME", appconfig.APP_NAME["en"])

    # Build one body per language, not per recipient.
    bodies = {}
    for key in {(lang, band) for _, lang, band in recipients}:
        bodies[key] = (
            build_text(edition, key[0], site_url, key[1]),
            build_html(edition, key[0], site_url, key[1]),
        )

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
        server.starttls()

    sent = 0
    with server:
        server.login(user, password)
        for addr, lang, band in recipients:
            text, html_body = bodies[(lang, band)]
            msg = EmailMessage()
            subject_date = pick(site.pretty_date(edition["date"]), lang)
            msg["Subject"] = f"{app_title(lang)} · {subject_date}"
            msg["From"] = formataddr((from_name, sender))
            msg["To"] = addr
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid()
            msg.set_content(text)
            msg.add_alternative(html_body, subtype="html")
            try:
                server.send_message(msg)
                print(f"  sent to {addr} ({lang}, {band})")
                sent += 1
            except smtplib.SMTPException as exc:
                # One bad address must not stop the rest of the family's copies.
                print(f"  FAILED for {addr}: {exc}", file=sys.stderr)
    return sent


def main() -> None:
    ap = argparse.ArgumentParser(description="Email one edition of Daily News for Kids.")
    ap.add_argument("--date", help="Edition date, YYYY-MM-DD. Defaults to the newest.")
    ap.add_argument("--force", action="store_true", help="Send even if already sent.")
    ap.add_argument("--to", help="Send only to this address, ignoring the list.")
    ap.add_argument("--lang", choices=["en", "zh"], default=CFG.primary_language,
                    help="Language for --to.")
    ap.add_argument("--band", choices=list(appconfig.AGE_BANDS), default=CFG.band,
                    help="Reading level for --to and --dry-run.")
    ap.add_argument("--dry-run", metavar="FILE", help="Write the HTML to FILE, send nothing.")
    args = ap.parse_args()

    if args.date:
        path = EDITIONS_DIR / f"{args.date}.json"
        if not path.exists():
            raise SystemExit(f"No edition for {args.date}.")
    else:
        available = sorted(EDITIONS_DIR.glob("*.json"))
        if not available:
            raise SystemExit("No editions to send.")
        path = available[-1]

    edition = json.loads(path.read_text(encoding="utf-8"))
    date_str = edition["date"]
    site_url = os.environ.get("SITE_URL") or CFG.site_url

    if args.dry_run:
        out = Path(args.dry_run)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(edition, args.lang, site_url, args.band), encoding="utf-8")
        size = out.stat().st_size
        print(f"Wrote {out} ({size / 1024:.0f} KB, {args.lang}, {args.band})")
        # Gmail truncates around 102 KB and hides the rest behind "View entire message".
        if size > 92_000:
            print("  warning: close to Gmail's 102 KB clipping threshold", file=sys.stderr)
        return

    if args.to:
        recipients = [(args.to, args.lang, args.band)]
    else:
        raw = os.environ.get("NEWSLETTER_RECIPIENTS", "")
        if not raw.strip():
            raise SystemExit("NEWSLETTER_RECIPIENTS is empty — nobody to send to.")
        recipients = parse_recipients(raw)
        if not recipients:
            raise SystemExit("NEWSLETTER_RECIPIENTS had no usable addresses.")

    if not args.force and not args.to and date_str in load_sent_log():
        print(f"{date_str} was already sent. Use --force to send it again.")
        return

    print(f"Sending {date_str} to {len(recipients)} recipient(s)…")
    count = send(edition, recipients, site_url)

    if count and not args.to:
        record_sent(date_str, count)
    print(f"Done: {count}/{len(recipients)} delivered.")


if __name__ == "__main__":
    main()
