# Daily News for Kids

**World news your child can actually read — and argue about.**

[中文说明](README.zh.md)

Every day at an hour you choose, this picks the most important stories from the
world's press, rewrites them for a child of the age you set, and publishes them
as a web page, an email, and a shareable image. Every story ends with three
dinner-table questions — and the case for **both sides** of each one, folded
away so your child answers first.

It runs entirely on GitHub Actions and GitHub Pages. There is no server, no
account, and no service in the middle. You own the repository and the content.

---

## What it makes, every day

| | |
| --- | --- |
| **A web page** | Today's edition plus a permalink per day and an archive, in one or two languages, light or dark. |
| **A newsletter** | The same edition by email to you and anyone you add, each reader in their own language. |
| **A share image** | A tall PNG for WeChat Moments and the like, ending in a QR code back to the full page. |

Each story carries a headline and a short summary; the full rewrite, words worth
knowing, background reading, further reading, videos, and the two-sided hints
all open on a click.

---

## Settings

Everything lives in one `config.toml`. Three ways to write it:

- open **`docs/setup.html`** in a browser and click through the form — it builds
  the file for you and nothing is sent anywhere;
- run **`python3 scripts/setup.py`** and answer the questions;
- or edit **`config.example.toml`** by hand.

```toml
[child]
name = "Lucas"      # optional, shown as "made for ___"
age  = 12           # 5-18

[edition]
count      = 3                    # 3-10 stories a day
categories = ["politics", "society", "business", "tech"]
regions    = ["US", "CN"]
languages  = ["en", "zh"]

[schedule]
timezone = "America/Vancouver"    # any IANA zone
hour     = 17                     # 0-23, local

[site]
url = "https://yourname.github.io/your-repo/"
```

**Beats** — `politics` `society` `business` `tech` `science` `environment`
`sports` `arts` `health` `education`. Each gets its own colour on the page, so a
glance says what kind of news a card is.

**Regions** — `US` `CN` `CA` `EU` `JPKR` `ANZ` `SEA` `SASIA` `LATAM` `MEA`, or
`GLOBAL` for all of them. News that is genuinely huge elsewhere — a major war
development, a Nobel Prize, a large disaster — gets in regardless of this list.

**Age** changes sentence length, how much gets explained, how many words go in
the word bank, and how hard the questions are. It does **not** change how
serious the news is allowed to be. A 7-year-old gets the Strait of Hormuz
explained with a distance they can picture, not a story about puppies instead.

**Count** stops at 10 on purpose. Past that it is no longer a digest.

**Schedule** takes any zone and any hour. Each edition covers the 24 hours
ending at that moment, so pick a time you are usually together.

---

## Settings a visitor can change

The site is static: each edition is written once, server-side, at your chosen
hour. So there are two kinds of setting and only one of them is a visitor's.

**Reading preferences** — language, appearance, which beats and regions to show,
how many stories — act on the page immediately. A settings dialog opens on a
browser's first visit and afterwards lives behind the gear in the top right.
Choices are stored per device in `localStorage`; a static page cannot see a
visitor's IP address, so a second device asks again.

**Publishing settings** — the child's age, how the news is written, how many
stories are produced, what time the edition is built — are decided when the
edition is generated. Those live in `config.toml` and take effect from the next
edition, not the one already on screen. The dialog says so and links to the full
form rather than offering controls that would appear to work.

---

## Setting it up

### 1. Take a copy

Fork this repository, or use **Use this template**. Everything below happens in
your copy's **Settings**.

### 2. Turn on the web page

**Settings → Pages → Deploy from a branch**, branch `main`, folder **`/docs`**.
Your address will be `https://<you>.github.io/<repo>/`. Put it in
`config.toml` under `[site] url` — the QR code on the share image points there.

### 3. Add an API key

Generate one at <https://console.anthropic.com>, then
**Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` | your key |

Without it the site still serves whatever is already there; it just stops
updating.

### 4. Email delivery (optional)

Get an **app password** — never your account password. Gmail needs two-factor
turned on first, then <https://myaccount.google.com/apppasswords>.

| Secret | Value |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` · `smtp-mail.outlook.com` · `smtp.mail.me.com` |
| `SMTP_PORT` | `587`, or `465` for implicit TLS |
| `SMTP_USER` | your full email address |
| `SMTP_PASSWORD` | the app password |
| `SMTP_FROM` | optional; defaults to `SMTP_USER` |
| `NEWSLETTER_RECIPIENTS` | see below |

Recipients are comma-separated, optionally with a language each:

```
lucas@example.com:en, mum@example.com:zh, grandpa@example.com:zh
```

Adding or removing a reader means editing that one secret. Addresses live in a
secret rather than a file on purpose — a public repository should not carry your
family's email addresses in its git history.

### 5. Run it once

**Actions → Daily edition → Run workflow.** A manual run ignores the clock, so
you do not have to wait until your chosen hour.

---

## How the day runs

```
config.toml
     │
     ▼
generate_edition.py   two Claude passes: search the world's press, then
     │                rewrite the top N for a child of the configured age
     ▼
data/editions/YYYY-MM-DD.json      ← the single source of truth
     │
     ├── build_poster.py    → docs/posters/YYYY-MM-DD-<lang>.png
     ├── render_site.py     → docs/  (page, permalink, archive, setup form)
     └── send_newsletter.py → email over SMTP
```

The workflow runs **hourly** and decides for itself whether this is your hour.
That is what lets any zone and any hour work, and it makes daylight saving a
non-event. It is also self-healing: an edition is due once the cutoff has passed
and today's is still missing, so a delayed or dropped run is picked up by the
next hour rather than losing the day.

Sending happens before the commit but is allowed to fail — the commit still
runs, so a mail outage costs one delivery, never a day's work. The job still
finishes red so you notice.

---

## Editorial rules

The rules are prose in `EDITORIAL_POLICY`, inside `scripts/generate_edition.py`.
Edit that text to change the paper's taste. In summary:

- **Importance means consequence, not drama** — how many people it affects, how
  long the effects last, whether something structural changed. Celebrity gossip
  is not a top story. Crime and gore are not top stories.
- **Spread across beats** when the ranking allows, but never fill a slot with a
  weak story to reach a beat.
- **Every URL must have appeared in a search result.** Constructing, guessing, or
  repairing a link is forbidden; an empty list beats an invented one. Videos are
  included only when a real one turned up.
- **Contested claims are labelled contested**, with both readings given.
- **Both sides of every question, argued at full strength** — never two good
  arguments and a weak one set up to be knocked down, and never a signal about
  which side the writer prefers, in the order, the labels, or the effort.

Two structural habits back that up: research and rewriting are separate passes,
so the rewrite can only use links the research actually found; and the hints stay
folded on the web and are left out of the email entirely, so a child meets the
question before anyone else's answer.

---

## Running it locally

```bash
pip install anthropic segno playwright opencv-python-headless
playwright install chromium

python3 scripts/setup.py                    # write config.toml
python3 scripts/generate_edition.py         # fetch and write today's edition
python3 scripts/build_poster.py --both      # share images
python3 scripts/render_site.py              # build docs/
python3 -m http.server -d docs 8000         # preview at localhost:8000
```

Useful flags:

```bash
python3 scripts/generate_edition.py --date 2026-08-16 --force
python3 scripts/generate_edition.py --dry-run
python3 scripts/render_site.py --single one-page.html
python3 scripts/send_newsletter.py --dry-run mail.html --lang zh
python3 scripts/send_newsletter.py --to you@example.com
python3 scripts/build_poster.py --keep-html
```

To write or fix an edition by hand, edit `data/editions/YYYY-MM-DD.json` and
re-run `render_site.py`. No API call needed.

### Cost

Two Claude calls a day — one research, one rewrite. Roughly a dollar or so per
edition at three stories, more as `count` and the number of beats grow.

---

## Layout

```
config.toml               your settings
config.example.toml       a commented starting point
data/editions/            one JSON file per day, the source of truth
data/sent.json            which days were emailed (dates and counts, no addresses)
scripts/
  appconfig.py            settings, beat and region catalogues, reading profiles
  setup.py                interactive setup
  setup_page.py           builds the browser setup form
  generate_edition.py     Claude API → edition JSON
  render_site.py          JSON → docs/
  build_poster.py         JSON → share image with a verified QR code
  send_newsletter.py      JSON → email over SMTP
  assets/                 stylesheet and toggles, copied into docs/assets
docs/                     generated; GitHub Pages serves this
.github/workflows/        the hourly job
```

`docs/` is generated — edit `scripts/assets/` or the JSON and re-render.

---

## Notes and limits

- **Check the sources.** The link rules make invented URLs unlikely, not
  impossible: a model can still cite a real page whose contents it has
  misremembered. Every story keeps its original link for exactly this reason.
- **Adding a beat** means one entry in `CATEGORIES` in `scripts/appconfig.py` —
  label, colours for both themes, and a one-line hint. Page CSS, the setup form,
  the poster, and the email all pick it up.
- **The share image needs `[site] url` set**, or its QR code points nowhere.
- The QR code is decoded back out of the finished PNG on every build and the
  build fails on a mismatch. A broken QR is invisible on review, so it is
  checked rather than eyeballed.
