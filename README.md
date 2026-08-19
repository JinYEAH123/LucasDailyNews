# Daily News for Kids

**Know big worlds. Train young minds.**

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

Almost nothing is a setting. Three stories a day, drawn from politics, society,
business, tech and science, centred on the US and China plus anything too big to
belong to one country — that is the editorial line, and it is the same for
everyone. Beats, regions and story count are deliberately not configurable.

What is configurable lives in one `config.toml`:

```toml
[child]
name = "Lucas"      # optional, shown as "made for ___"
age  = 12           # 5-18 — picks which reading level the page opens on

[edition]
languages = ["en", "zh"]

[schedule]
timezone = "America/Vancouver"    # any IANA zone
hour     = 17                     # 0-23, local

[site]
url = "https://yourname.github.io/your-repo/"
```

Three ways to write it: open **`docs/setup.html`** in a browser, run
**`python3 scripts/setup.py`**, or edit **`config.example.toml`** by hand.

## Reading levels

Every edition is written three times — for **ages 6–11, 12–15 and 16+** — and all
three ship in the same page. Switching between them is one attribute on the root
element, so it is instant, works offline, and needs no server.

What changes between bands is sentence length, how much scaffolding a fact needs,
how many words go in the word bank, and how hard the dinner questions are. What
does **not** change is which stories are told or how serious they are allowed to
be. A seven-year-old gets the Strait of Hormuz explained with a distance they can
picture — not a story about puppies instead.

`[child] age` only decides which band the page opens on. Any reader can switch
with the control at the top, and the choice is remembered on that device.

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

Recipients are comma-separated, optionally with a language and a reading level
each — which is how one household sends different levels to different children:

```
lucas@example.com:en:12-15, mia@example.com:en:6-11, mum@example.com:zh
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
generate_edition.py   research the world's press, record the three stories
     │                and their links once, then write each reading level
     ▼
data/editions/YYYY-MM-DD.json      ← the single source of truth
     │
     ├── build_poster.py    → docs/posters/YYYY-MM-DD-<lang>-<band>.png
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
pip install anthropic jsonschema segno playwright opencv-python-headless
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

Five Claude calls a day: one research pass, one that records the chosen stories
and their links, and one per reading level. Roughly $2–3 a day, so on the order
of $60–90 a month. Writing three bands is most of that — a single-band build
would be about a third.

---

## Layout

```
config.toml               your settings
config.example.toml       a commented starting point
data/editions/            one JSON file per day, the source of truth
data/sent.json            which days were emailed (dates and counts, no addresses)
scripts/
  appconfig.py            settings, beat and region catalogues, age bands
  setup.py                interactive setup
  setup_page.py           builds the browser setup form
  generate_edition.py     Claude API → edition JSON (all three bands)
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
- **Adding a beat or a reading level** means one entry in `CATEGORIES` or
  `AGE_BANDS` in `scripts/appconfig.py`. The page CSS, the band switcher, the
  output schema, the poster and the email are all generated from those tables.
- **The share image needs `[site] url` set**, or its QR code points nowhere.
- The QR code is decoded back out of the finished PNG on every build and the
  build fails on a mismatch. A broken QR is invisible on review, so it is
  checked rather than eyeballed.
