#!/usr/bin/env python3
"""Build docs/setup.html — the form a parent fills in to configure their own copy.

It is a static page: pick the options, and it writes the config.toml text for
you to paste into the repository. No backend, nothing submitted anywhere.
"""

from __future__ import annotations

import html
import json

import appconfig

TEMPLATE = """<!doctype html>
<html lang="__LANG__" data-lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set up Daily News for Kids</title>
<meta name="description" content="__SLOGAN__">
__FONTS__
<link rel="stylesheet" href="assets/styles.css">
<style>
__BEATCSS__
.setup-section { margin: 2rem 0 0; }
.setup-section > h2 {
  font-family: var(--display); font-weight: 600; font-size: 1.15rem;
  margin: 0 0 .2rem; letter-spacing: -.01em;
}
.setup-section > .note { margin: 0 0 .8rem; font-size: .87rem; color: var(--ink-faint); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(13.5rem, 1fr)); gap: .5rem; }
.opt {
  display: flex; gap: .6rem; align-items: flex-start; cursor: pointer;
  border: 1px solid var(--rule); border-radius: 10px; padding: .65rem .75rem;
  background: var(--card); transition: border-color .15s, background-color .15s;
}
.opt:hover { border-color: var(--ink-faint); }
.opt input { margin: .25rem 0 0; accent-color: var(--dot, var(--chrome)); flex: none; }
.opt:has(input:checked) { border-color: var(--dot, var(--chrome)); background: var(--tint, var(--card)); }
.opt .name { font-weight: 600; font-size: .92rem; display: flex; align-items: center; gap: .45rem; }
.opt .dot { width: .55rem; height: .55rem; border-radius: 50%; background: var(--dot); flex: none; }
.opt .hint { display: block; font-size: .8rem; color: var(--ink-faint); margin-top: .15rem; }
.row { display: flex; gap: .8rem; flex-wrap: wrap; align-items: flex-end; }
.field { display: flex; flex-direction: column; gap: .3rem; }
.field label { font-size: .8rem; font-weight: 600; color: var(--ink-soft); }
.field input, .field select {
  font: inherit; font-size: .95rem; padding: .45rem .6rem; border-radius: 8px;
  border: 1px solid var(--rule); background: var(--card); color: var(--ink);
}
.field input[type=text] { min-width: 15rem; }
output.pill {
  display: inline-block; font-weight: 700; color: var(--chrome);
  font-variant-numeric: tabular-nums;
}
pre.out {
  background: var(--card); border: 1px solid var(--rule); border-radius: 12px;
  padding: 1rem 1.1rem; overflow-x: auto; font-size: .84rem; line-height: 1.6;
  white-space: pre; margin: 0;
}
.outbar { display: flex; gap: .6rem; align-items: center; margin: 0 0 .6rem; flex-wrap: wrap; }
button.copy {
  font: inherit; font-size: .85rem; font-weight: 600; padding: .4rem .9rem;
  border-radius: 999px; border: 1px solid var(--chrome); background: var(--chrome);
  color: var(--chrome-on); cursor: pointer;
}
.warn { color: var(--politics); font-size: .85rem; font-weight: 600; }
.preview-note { font-size: .87rem; color: var(--ink-soft); margin: .5rem 0 0; }
</style>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22><text y=%2214%22 font-size=%2214%22>📰</text></svg>">
</head>
<body>
<div class="wrap">
<header class="masthead">
  <h1>__TITLE__</h1>
  <p class="tagline">__SLOGAN__</p>
  <p class="for-line">__INTRO__</p>
  <div class="controls">
    __LANGBTNS__
    <button type="button" data-theme-toggle>__THEME__</button>
__TODAYBTN__
  </div>
</header>

<form id="f">
  <section class="setup-section">
    <h2>__H_CHILD__</h2>
    <p class="note">__N_CHILD__</p>
    <div class="row">
      <div class="field">
        <label for="name">__L_NAME__</label>
        <input type="text" id="name" value="__NAME__">
      </div>
      <div class="field">
        <label for="age">__L_AGE__ <output class="pill" id="ageOut">__AGE__</output></label>
        <input type="range" id="age" min="5" max="18" value="__AGE__">
      </div>
      <div class="field">
        <label for="count">__L_COUNT__ <output class="pill" id="countOut">__COUNT__</output></label>
        <input type="range" id="count" min="3" max="10" value="__COUNT__">
      </div>
    </div>
  </section>

  <section class="setup-section">
    <h2>__H_CATS__</h2>
    <p class="note">__N_CATS__</p>
    <div class="grid" id="cats"></div>
  </section>

  <section class="setup-section">
    <h2>__H_REGIONS__</h2>
    <p class="note">__N_REGIONS__</p>
    <div class="grid" id="regions"></div>
  </section>

  <section class="setup-section">
    <h2>__H_WHEN__</h2>
    <p class="note">__N_WHEN__</p>
    <div class="row">
      <div class="field">
        <label for="tz">__L_TZ__</label>
        <select id="tz"></select>
      </div>
      <div class="field">
        <label for="hour">__L_HOUR__</label>
        <select id="hour"></select>
      </div>
    </div>
    <p class="preview-note" id="whenPreview"></p>
  </section>

  <section class="setup-section">
    <h2>__H_LANGS__</h2>
    <p class="note">__N_LANGS__</p>
    <div class="grid" id="langs"></div>
  </section>

  <section class="setup-section">
    <h2>__H_SITE__</h2>
    <p class="note">__N_SITE__</p>
    <div class="field">
      <label for="url">__L_URL__</label>
      <input type="text" id="url" value="__URL__" placeholder="https://yourname.github.io/your-repo/">
    </div>
  </section>
</form>

<section class="setup-section">
  <h2>__H_OUT__</h2>
  <p class="note">__N_OUT__</p>
  <div class="outbar">
    <button class="copy" type="button" id="copy">__B_COPY__</button>
    <span id="status" class="preview-note"></span>
    <span id="warn" class="warn"></span>
  </div>
  <pre class="out" id="out"></pre>
</section>

<footer class="foot">__FOOT__</footer>
</div>

<script src="assets/app.js"></script>
<script>
(function () {
  var CATS = __CATS_JSON__;
  var REGIONS = __REGIONS_JSON__;
  var LANGS = __LANGS_JSON__;
  var TEXT = __TEXT_JSON__;
  var lang = document.documentElement.getAttribute('data-lang') || 'en';

  function label(obj) { return obj[lang] || obj.en; }

  function makeOption(container, kind, key, entry, checked) {
    var id = kind + '-' + key;
    var wrap = document.createElement('label');
    wrap.className = 'opt';
    if (entry.color) { wrap.style.setProperty('--dot', entry.color); wrap.style.setProperty('--tint', entry.tint); }
    var box = document.createElement('input');
    box.type = 'checkbox'; box.id = id; box.value = key; box.checked = checked;
    var text = document.createElement('span');
    var name = document.createElement('span');
    name.className = 'name';
    if (entry.color) {
      var dot = document.createElement('span');
      dot.className = 'dot';
      name.appendChild(dot);
    }
    name.appendChild(document.createTextNode(label(entry.label)));
    text.appendChild(name);
    if (entry.hint) {
      var hint = document.createElement('span');
      hint.className = 'hint';
      hint.textContent = label(entry.hint);
      text.appendChild(hint);
    }
    wrap.appendChild(box); wrap.appendChild(text);
    container.appendChild(wrap);
    return box;
  }

  var catBoxes = {}, regionBoxes = {}, langBoxes = {};
  Object.keys(CATS).forEach(function (k) {
    catBoxes[k] = makeOption(document.getElementById('cats'), 'c', k, CATS[k], CATS[k].on);
  });
  Object.keys(REGIONS).forEach(function (k) {
    regionBoxes[k] = makeOption(document.getElementById('regions'), 'r', k, REGIONS[k], REGIONS[k].on);
  });
  Object.keys(LANGS).forEach(function (k) {
    langBoxes[k] = makeOption(document.getElementById('langs'), 'l', k, LANGS[k], LANGS[k].on);
  });

  // Ticking "Global" means everywhere, so it drives the rest of the boxes.
  var globalBox = regionBoxes.GLOBAL;
  if (globalBox) {
    globalBox.addEventListener('change', function () {
      Object.keys(regionBoxes).forEach(function (k) {
        if (k !== 'GLOBAL') regionBoxes[k].checked = globalBox.checked;
      });
      render();
    });
    Object.keys(regionBoxes).forEach(function (k) {
      if (k === 'GLOBAL') return;
      regionBoxes[k].addEventListener('change', function () {
        if (!regionBoxes[k].checked) globalBox.checked = false;
        render();
      });
    });
  }

  // Time zones straight from the browser, defaulting to where the parent is.
  var tzSelect = document.getElementById('tz');
  var zones = [];
  try { zones = Intl.supportedValuesOf('timeZone'); } catch (e) { zones = []; }
  var here = __TZ_JSON__;
  try { here = Intl.DateTimeFormat().resolvedOptions().timeZone || here; } catch (e) {}
  if (!zones.length) zones = [here, 'America/Vancouver', 'America/New_York', 'America/Los_Angeles',
    'Europe/London', 'Europe/Paris', 'Asia/Shanghai', 'Asia/Tokyo', 'Australia/Sydney'];
  if (zones.indexOf(here) === -1) zones.unshift(here);
  zones.forEach(function (z) {
    var o = document.createElement('option');
    o.value = z; o.textContent = z; if (z === here) o.selected = true;
    tzSelect.appendChild(o);
  });

  var hourSelect = document.getElementById('hour');
  for (var h = 0; h < 24; h++) {
    var o = document.createElement('option');
    o.value = h;
    var ampm = h === 0 ? '12 AM' : h < 12 ? h + ' AM' : h === 12 ? '12 PM' : (h - 12) + ' PM';
    o.textContent = (h < 10 ? '0' + h : h) + ':00  ·  ' + ampm;
    if (h === __HOUR__) o.selected = true;
    hourSelect.appendChild(o);
  }

  function checkedKeys(boxes, skip) {
    return Object.keys(boxes).filter(function (k) {
      return boxes[k].checked && k !== skip;
    });
  }

  function toml(list) {
    return '[' + list.map(function (s) { return '"' + s + '"'; }).join(', ') + ']';
  }

  function render() {
    var name = document.getElementById('name').value.trim();
    var age = document.getElementById('age').value;
    var count = document.getElementById('count').value;
    document.getElementById('ageOut').textContent = age;
    document.getElementById('countOut').textContent = count;

    var cats = checkedKeys(catBoxes);
    var regions = globalBox && globalBox.checked ? ['GLOBAL'] : checkedKeys(regionBoxes, 'GLOBAL');
    var langs = checkedKeys(langBoxes);
    var tz = tzSelect.value;
    var hour = hourSelect.value;
    var url = document.getElementById('url').value.trim();

    var problems = [];
    if (!cats.length) problems.push(TEXT.needCat[lang] || TEXT.needCat.en);
    if (!regions.length) problems.push(TEXT.needRegion[lang] || TEXT.needRegion.en);
    if (!langs.length) problems.push(TEXT.needLang[lang] || TEXT.needLang.en);
    document.getElementById('warn').textContent = problems.join(' · ');

    var start = (Number(hour) + 24 - 24) % 24;
    var pv = (TEXT.whenPreview[lang] || TEXT.whenPreview.en)
      .replace('{hour}', (hour < 10 ? '0' + hour : hour) + ':00')
      .replace('{tz}', tz);
    document.getElementById('whenPreview').textContent = pv;

    var lines = [
      '# Daily News for Kids — generated by the setup form.',
      '# Save this as config.toml in the root of your repository.',
      '',
      '[child]',
      'name = "' + name.replace(/"/g, '') + '"',
      'age = ' + age,
      '',
      '[edition]',
      'count = ' + count,
      'categories = ' + toml(cats),
      'regions = ' + toml(regions),
      'languages = ' + toml(langs),
      '',
      '[schedule]',
      'timezone = "' + tz + '"',
      'hour = ' + hour,
      '',
      '[site]',
      'url = "' + url.replace(/"/g, '') + '"',
      ''
    ];
    document.getElementById('out').textContent = lines.join('\\n');
  }

  document.getElementById('f').addEventListener('input', render);
  document.getElementById('f').addEventListener('change', render);
  document.addEventListener('click', function (ev) {
    if (ev.target.closest('[data-lang-set]')) {
      lang = document.documentElement.getAttribute('data-lang') || 'en';
      setTimeout(render, 0);
    }
  });

  document.getElementById('copy').addEventListener('click', function () {
    var text = document.getElementById('out').textContent;
    var done = function () {
      var s = document.getElementById('status');
      s.textContent = TEXT.copied[lang] || TEXT.copied.en;
      setTimeout(function () { s.textContent = ''; }, 2500);
    };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done, done);
    } else {
      var ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta); done();
    }
  });

  render();
})();
</script>
</body>
</html>
"""

TEXT = {
    "intro": {
        "en": "Fill this in, copy the result into config.toml, and it becomes your child's paper.",
        "zh": "填好这张表，把结果复制到 config.toml，它就变成你孩子的那份报纸。",
    },
    "h_child": {"en": "Who is reading", "zh": "谁在读"},
    "n_child": {
        "en": "Age changes how the news is written — sentence length, how much gets "
              "explained, and how hard the dinner questions are. It never changes how "
              "serious the news is allowed to be.",
        "zh": "年龄会改变新闻的写法——句子长短、要解释到什么程度、饭桌问题的难度。"
              "它不会改变新闻本身可以有多严肃。",
    },
    "l_name": {"en": "Child's name (optional)", "zh": "孩子的名字（可留空）"},
    "l_age": {"en": "Age", "zh": "年龄"},
    "l_count": {"en": "Stories per day", "zh": "每天几条"},
    "h_cats": {"en": "What to cover", "zh": "覆盖哪些板块"},
    "n_cats": {
        "en": "Pick as many as you like. Each beat gets its own colour on the page, "
              "so a glance tells you what kind of news it is.",
        "zh": "想选几个都可以。每个板块在页面上有自己的颜色，一眼就知道是哪类新闻。",
    },
    "h_regions": {"en": "Where in the world", "zh": "关注哪些地区"},
    "n_regions": {
        "en": "Anything genuinely huge elsewhere still gets in — a major war "
              "development, a Nobel Prize, a large disaster. Ticking Global selects "
              "everything.",
        "zh": "别处真正重大的事仍然会进来——重大战事、诺贝尔奖、大型灾害。"
              "勾选「全球」等于全选。",
    },
    "h_when": {"en": "When it arrives", "zh": "什么时候更新"},
    "n_when": {
        "en": "Your own time zone is filled in already. Each edition covers the 24 "
              "hours ending at this time, so pick a moment you are usually together.",
        "zh": "已经自动填好了你所在的时区。每一期覆盖截至这个时刻的 24 小时，"
              "所以挑一个你们通常在一起的时间。",
    },
    "l_tz": {"en": "Time zone", "zh": "时区"},
    "l_hour": {"en": "Time of day", "zh": "更新时刻"},
    "h_langs": {"en": "Languages", "zh": "语言"},
    "n_langs": {
        "en": "Pick both and the page gets a toggle — handy when the child reads one "
              "language at school and the family reads another at home.",
        "zh": "两个都选，页面上会出现切换按钮——孩子在学校读一种语言、家里读另一种时很好用。",
    },
    "h_site": {"en": "Where it will live", "zh": "发布在哪里"},
    "n_site": {
        "en": "Your GitHub Pages address. The QR code on the share image points here, "
              "so fill it in before sharing an image anywhere.",
        "zh": "你的 GitHub Pages 地址。转发长图上的二维码指向这里，所以分享之前要先填好。",
    },
    "l_url": {"en": "Site address", "zh": "网站地址"},
    "h_out": {"en": "Your config.toml", "zh": "你的 config.toml"},
    "n_out": {
        "en": "Copy this into config.toml in the root of your repository, then run the "
              "workflow once to see the first edition.",
        "zh": "把它复制进仓库根目录的 config.toml，然后手动跑一次工作流，就能看到第一期。",
    },
    "b_copy": {"en": "Copy", "zh": "复制"},
    "copied": {"en": "Copied.", "zh": "已复制。"},
    "needCat": {"en": "Pick at least one beat.", "zh": "至少选一个板块。"},
    "needRegion": {"en": "Pick at least one region.", "zh": "至少选一个地区。"},
    "needLang": {"en": "Pick at least one language.", "zh": "至少选一种语言。"},
    "whenPreview": {
        "en": "Each edition covers the 24 hours ending at {hour} in {tz}.",
        "zh": "每一期覆盖 {tz} 时区里截至 {hour} 的 24 小时。",
    },
    "foot": {
        "en": "Nothing here is sent anywhere — the page builds the text in your browser.",
        "zh": "这里填的内容不会发送到任何地方——文本是在你的浏览器里生成的。",
    },
    "theme": {"en": "Light / Dark", "zh": "浅色 / 深色"},
    "today": {"en": "Today", "zh": "今日"},
}


def _bi(key: str, langs: list) -> str:
    """Bilingual spans matching the site's language toggle."""
    entry = TEXT[key]
    return "".join(
        f'<span class="l-{l}">{entry.get(l, entry["en"])}</span>' for l in langs
    )


def render(inline: bool = False) -> str:
    """Build the setup form.

    inline=True returns a self-contained fragment — stylesheet and toggles
    embedded, no links to the rest of the site — so the form can be published
    or emailed on its own to someone who does not have the repository yet.
    """
    import render_site

    cfg = render_site.CFG
    langs = cfg.languages

    cats = {
        k: {
            "label": v["label"],
            "hint": v["hint"],
            "color": v["light"][0],
            "tint": v["light"][1],
            "on": k in cfg.categories,
        }
        for k, v in appconfig.CATEGORIES.items()
    }
    regions = {
        k: {"label": v["label"], "on": (k in cfg.regions) or
            (k == "GLOBAL" and set(cfg.regions) == set(appconfig.COUNTRY_REGIONS))}
        for k, v in appconfig.REGIONS.items()
    }
    languages = {
        k: {"label": {"en": v, "zh": v}, "on": k in cfg.languages}
        for k, v in appconfig.LANGUAGES.items()
    }

    out = TEMPLATE
    replacements = {
        "__LANG__": langs[0],
        "__FONTS__": render_site.FONTS,
        "__BEATCSS__": render_site.beat_css(),
        "__TITLE__": "".join(
            f'<span class="l-{l}">{appconfig.APP_NAME.get(l, appconfig.APP_NAME["en"])}</span>'
            for l in langs),
        "__SLOGAN__": "".join(
            f'<span class="l-{l}">{appconfig.SLOGAN.get(l, appconfig.SLOGAN["en"])}</span>'
            for l in langs),
        "__LANGBTNS__": render_site.lang_buttons(),
        "__CATS_JSON__": json.dumps(cats, ensure_ascii=False),
        "__REGIONS_JSON__": json.dumps(regions, ensure_ascii=False),
        "__LANGS_JSON__": json.dumps(languages, ensure_ascii=False),
        "__TEXT_JSON__": json.dumps(TEXT, ensure_ascii=False),
        "__NAME__": html.escape(cfg.child_name, quote=True),
        "__AGE__": str(cfg.age),
        "__COUNT__": str(cfg.count),
        "__URL__": html.escape(cfg.site_url, quote=True),
        "__HOUR__": str(cfg.hour),
        "__TZ_JSON__": json.dumps(cfg.timezone),
        "__TODAYBTN__": "" if inline else
                        f'<a class="btn" href="index.html">{_bi("today", langs)}</a>',
    }
    for key in ("intro", "h_child", "n_child", "l_name", "l_age", "l_count",
                "h_cats", "n_cats", "h_regions", "n_regions", "h_when", "n_when",
                "l_tz", "l_hour", "h_langs", "n_langs", "h_site", "n_site",
                "l_url", "h_out", "n_out", "b_copy", "foot", "theme", "today"):
        replacements["__" + key.upper() + "__"] = _bi(key, langs)

    # The meta description cannot hold markup.
    out = out.replace('content="__SLOGAN__"',
                      f'content="{appconfig.SLOGAN.get(langs[0], appconfig.SLOGAN["en"])}"')
    for token, value in replacements.items():
        out = out.replace(token, value)

    if not inline:
        return out

    # Inline the shared assets, then hand back only what the Artifact wrapper
    # does not already provide (it supplies <html>, <head> and <body>).
    assets = render_site.ASSETS_SRC
    out = out.replace(
        '<link rel="stylesheet" href="assets/styles.css">',
        "<style>" + (assets / "styles.css").read_text(encoding="utf-8") + "</style>")
    out = out.replace(
        '<script src="assets/app.js"></script>',
        "<script>" + (assets / "app.js").read_text(encoding="utf-8") + "</script>")

    head = out[out.index("<title>"):out.index("</head>")]
    body = out[out.index("<body>") + len("<body>"):out.index("</body>")]
    return head + body


if __name__ == "__main__":
    print(render())
