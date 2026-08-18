#!/usr/bin/env python3
"""Build docs/setup.html — the form a repository owner fills in to configure
their own copy.

Deliberately short. Beats, regions and story count are the product's editorial
line, not settings, so the only things here are who is reading, in what
language, and when the edition lands.
"""

from __future__ import annotations

import html
import json

import appconfig

TEXT = {
    "intro": {
        "en": "Fill this in, copy the result into config.toml, and it becomes your "
              "child's paper from the next edition on.",
        "zh": "填好这张表，把结果复制到 config.toml，从下一期开始它就是你孩子的那份报纸。",
    },
    "h_child": {"en": "Who is reading", "zh": "谁在读"},
    "n_child": {
        "en": "Every edition is written at all three reading levels, so this only "
              "picks which one the page opens on. Anyone can switch on the page itself.",
        "zh": "每一期都会按三个阅读难度各写一遍，所以这里只是决定页面默认打开哪一个。"
              "任何人都可以在页面上自己切换。",
    },
    "l_name": {"en": "Child's name (optional)", "zh": "孩子的名字（可留空）"},
    "l_age": {"en": "Age", "zh": "年龄"},
    "band_is": {"en": "Opens on", "zh": "默认打开"},
    "h_langs": {"en": "Languages", "zh": "语言"},
    "n_langs": {
        "en": "Pick both and the page gets a toggle — handy when the child reads one "
              "language at school and the family reads another at home.",
        "zh": "两个都选，页面上会出现切换按钮——孩子在学校读一种语言、家里读另一种时很好用。",
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
    "h_site": {"en": "Where it will live", "zh": "发布在哪里"},
    "n_site": {
        "en": "Your GitHub Pages address. The QR code on the share image points here, "
              "so fill it in before sharing an image anywhere.",
        "zh": "你的 GitHub Pages 地址。转发长图上的二维码指向这里，所以分享之前要先填好。",
    },
    "l_url": {"en": "Site address", "zh": "网站地址"},
    "h_out": {"en": "Your config.toml", "zh": "你的 config.toml"},
    "n_out": {
        "en": "Copy this into config.toml in the root of your repository and commit. "
              "The next edition follows it.",
        "zh": "把它复制进仓库根目录的 config.toml 并提交。下一期就会按它来。",
    },
    "b_copy": {"en": "Copy", "zh": "复制"},
    "copied": {"en": "Copied.", "zh": "已复制。"},
    "needLang": {"en": "Pick at least one language.", "zh": "至少选一种语言。"},
    "whenPreview": {
        "en": "Each edition covers the 24 hours ending at {hour} in {tz}.",
        "zh": "每一期覆盖 {tz} 时区里截至 {hour} 的 24 小时。",
    },
    "fixed_h": {"en": "What is not a setting", "zh": "哪些不是设置项"},
    "fixed_n": {
        "en": "Three stories a day, drawn from politics, society, business, tech and "
              "science, centred on the US and China plus anything too big to belong to "
              "one country. That is the editorial line rather than a preference, so it "
              "is the same for everyone.",
        "zh": "每天三条，取自政治、社会、财经、科技、科学，以美国和中国为重心，"
              "外加大到不属于任何单一国家的事件。这是编辑方针，不是偏好设置，所以对所有人都一样。",
    },
    "foot": {
        "en": "Nothing here is sent anywhere — the page builds the text in your browser.",
        "zh": "这里填的内容不会发送到任何地方——文本是在你的浏览器里生成的。",
    },
    "theme": {"en": "Light / Dark", "zh": "浅色 / 深色"},
    "today": {"en": "Today", "zh": "今日"},
}

TEMPLATE = """<!doctype html>
<html lang="__LANG__" data-lang="__LANG__" data-band="__BAND__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set up Daily News for Kids</title>
<meta name="description" content="__SLOGAN_PLAIN__">
__FONTS__
<link rel="stylesheet" href="assets/styles.css">
<style>
__GENCSS__
.setup-section { margin: 2rem 0 0; }
.setup-section > h2 {
  font-family: var(--display); font-weight: 600; font-size: 1.15rem;
  margin: 0 0 .2rem; letter-spacing: -.01em;
}
.setup-section > .note { margin: 0 0 .9rem; font-size: .87rem; line-height: 1.6; color: var(--ink-faint); }
.row { display: flex; gap: .9rem; flex-wrap: wrap; align-items: flex-end; }
.field { display: flex; flex-direction: column; gap: .3rem; }
.field label { font-size: .8rem; font-weight: 600; color: var(--ink-soft); }
.field input, .field select {
  font: inherit; font-size: .95rem; padding: .45rem .6rem; border-radius: 8px;
  border: 1px solid var(--rule); background: var(--card); color: var(--ink);
}
.field input[type=text] { min-width: 16rem; }
.field input[type=range] { min-width: 13rem; accent-color: var(--chrome); }
output.pill { font-weight: 700; color: var(--chrome); font-variant-numeric: tabular-nums; }
.opt {
  display: inline-flex; gap: .5rem; align-items: center; cursor: pointer;
  border: 1px solid var(--rule); border-radius: 10px; padding: .55rem .8rem;
  background: var(--card); font-size: .92rem; font-weight: 600;
}
.opt:has(input:checked) { border-color: var(--chrome); }
.opt input { accent-color: var(--chrome); }
pre.out {
  background: var(--card); border: 1px solid var(--rule); border-radius: 12px;
  padding: 1rem 1.1rem; overflow-x: auto; font-size: .82rem; line-height: 1.6;
  white-space: pre; margin: 0;
}
.outbar { display: flex; gap: .6rem; align-items: center; margin: 0 0 .6rem; flex-wrap: wrap; }
button.copy {
  font: inherit; font-size: .85rem; font-weight: 600; padding: .4rem .9rem;
  border-radius: 999px; border: 1px solid var(--chrome); background: var(--chrome);
  color: var(--chrome-on); cursor: pointer;
}
.warn { color: var(--politics); font-size: .85rem; font-weight: 600; }
.preview-note { font-size: .87rem; color: var(--ink-soft); margin: .6rem 0 0; }
.fixed-box {
  border: 1px dashed var(--rule); border-radius: 12px; padding: .9rem 1.05rem;
  font-size: .87rem; line-height: 1.65; color: var(--ink-soft);
}
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
    <a class="btn" href="index.html">__TODAY__</a>
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
        <input type="range" id="age" min="__MINAGE__" max="__MAXAGE__" value="__AGE__">
      </div>
    </div>
    <p class="preview-note" id="bandPreview"></p>
  </section>

  <section class="setup-section">
    <h2>__H_LANGS__</h2>
    <p class="note">__N_LANGS__</p>
    <div class="row" id="langs"></div>
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

<section class="setup-section">
  <h2>__FIXED_H__</h2>
  <p class="fixed-box">__FIXED_N__</p>
</section>

<footer class="foot">__FOOT__</footer>
</div>

<script src="assets/app.js"></script>
<script>
(function () {
  var LANGS = __LANGS_JSON__;
  var BANDS = __BANDS_JSON__;
  var TEXT = __TEXT_JSON__;
  var lang = document.documentElement.getAttribute('data-lang') || 'en';
  function tr(key) { var e = TEXT[key] || {}; return e[lang] || e.en || ''; }

  var langBox = document.getElementById('langs');
  var boxes = {};
  LANGS.forEach(function (l) {
    var wrap = document.createElement('label');
    wrap.className = 'opt';
    var input = document.createElement('input');
    input.type = 'checkbox'; input.id = 'l-' + l.code; input.checked = l.on;
    wrap.appendChild(input);
    wrap.appendChild(document.createTextNode(l.label));
    langBox.appendChild(wrap);
    boxes[l.code] = input;
  });

  var tzSelect = document.getElementById('tz');
  var zones = [];
  try { zones = Intl.supportedValuesOf('timeZone'); } catch (e) { zones = []; }
  var here = __TZ_JSON__;
  try { here = Intl.DateTimeFormat().resolvedOptions().timeZone || here; } catch (e) {}
  if (!zones.length) zones = [here, 'America/Vancouver', 'America/New_York',
    'Europe/London', 'Asia/Shanghai', 'Asia/Tokyo', 'Australia/Sydney'];
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

  function bandFor(age) {
    for (var i = 0; i < BANDS.length; i++) {
      if (age >= BANDS[i].min && age <= BANDS[i].max) return BANDS[i];
    }
    return BANDS[BANDS.length - 1];
  }

  function render() {
    var name = document.getElementById('name').value.trim();
    var age = Number(document.getElementById('age').value);
    document.getElementById('ageOut').textContent = age;

    var band = bandFor(age);
    document.getElementById('bandPreview').textContent =
      tr('band_is') + ': ' + (band.label[lang] || band.label.en);
    // The band is derived from the age, never stored separately — one number,
    // one source of truth, and no way for the two to disagree.
    document.documentElement.setAttribute('data-band', band.key);

    var langs = LANGS.map(function (l) { return l.code; })
                     .filter(function (c) { return boxes[c].checked; });
    document.getElementById('warn').textContent = langs.length ? '' : tr('needLang');

    var tz = tzSelect.value, hour = hourSelect.value;
    document.getElementById('whenPreview').textContent = tr('whenPreview')
      .replace('{hour}', (hour < 10 ? '0' + hour : hour) + ':00')
      .replace('{tz}', tz);

    document.getElementById('out').textContent = [
      '# Daily News for Kids — generated by the setup form.',
      '# Save this as config.toml in the root of your repository.',
      '',
      '[child]',
      'name = "' + name.replace(/"/g, '') + '"',
      'age = ' + age,
      '',
      '[edition]',
      'languages = [' + langs.map(function (c) { return '"' + c + '"'; }).join(', ') + ']',
      '',
      '[schedule]',
      'timezone = "' + tz + '"',
      'hour = ' + hour,
      '',
      '[site]',
      'url = "' + document.getElementById('url').value.trim().replace(/"/g, '') + '"',
      ''
    ].join('\\n');
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
      s.textContent = tr('copied');
      setTimeout(function () { s.textContent = ''; }, 2400);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, done);
    else {
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


def _bi(key: str, langs: list) -> str:
    entry = TEXT[key]
    return "".join(f'<span class="l-{l}">{entry.get(l, entry["en"])}</span>' for l in langs)


def render(inline: bool = False) -> str:
    """inline=True returns a self-contained fragment for publishing on its own."""
    import render_site

    cfg = render_site.CFG
    langs = cfg.languages

    bands = [
        {"key": k, "min": v["range"][0], "max": v["range"][1], "label": v["label"]}
        for k, v in appconfig.AGE_BANDS.items()
    ]
    languages = [{"code": k, "label": v, "on": k in langs}
                 for k, v in appconfig.LANGUAGES.items()]

    out = TEMPLATE
    replacements = {
        "__LANG__": langs[0],
        "__BAND__": cfg.band,
        "__FONTS__": render_site.FONTS,
        "__GENCSS__": render_site.generated_css(),
        "__SLOGAN_PLAIN__": appconfig.SLOGAN.get(langs[0], appconfig.SLOGAN["en"]),
        "__TITLE__": "".join(
            f'<span class="l-{l}">{appconfig.APP_NAME.get(l, appconfig.APP_NAME["en"])}</span>'
            for l in langs),
        "__SLOGAN__": "".join(
            f'<span class="l-{l}">{appconfig.SLOGAN.get(l, appconfig.SLOGAN["en"])}</span>'
            for l in langs),
        "__LANGBTNS__": render_site.lang_buttons(),
        "__LANGS_JSON__": json.dumps(languages, ensure_ascii=False),
        "__BANDS_JSON__": json.dumps(bands, ensure_ascii=False),
        "__TEXT_JSON__": json.dumps(TEXT, ensure_ascii=False),
        "__TZ_JSON__": json.dumps(cfg.timezone),
        "__NAME__": html.escape(cfg.child_name, quote=True),
        "__AGE__": str(cfg.age),
        "__MINAGE__": str(appconfig.MIN_AGE),
        "__MAXAGE__": str(appconfig.MAX_AGE),
        "__HOUR__": str(cfg.hour),
        "__URL__": html.escape(cfg.site_url, quote=True),
    }
    for key in ("intro", "h_child", "n_child", "l_name", "l_age", "h_langs", "n_langs",
                "h_when", "n_when", "l_tz", "l_hour", "h_site", "n_site", "l_url",
                "h_out", "n_out", "b_copy", "fixed_h", "fixed_n", "foot", "theme", "today"):
        replacements["__" + key.upper() + "__"] = _bi(key, langs)

    for token, value in replacements.items():
        out = out.replace(token, value)

    if not inline:
        return out

    assets = render_site.ASSETS_SRC
    out = out.replace('<link rel="stylesheet" href="assets/styles.css">',
                      "<style>" + (assets / "styles.css").read_text(encoding="utf-8") + "</style>")
    out = out.replace('<script src="assets/app.js"></script>',
                      "<script>" + (assets / "app.js").read_text(encoding="utf-8") + "</script>")
    out = out.replace('<a class="btn" href="index.html">' + _bi("today", langs) + '</a>', "")
    head = out[out.index("<title>"):out.index("</head>")]
    body = out[out.index("<body>") + len("<body>"):out.index("</body>")]
    return (f'<script>document.documentElement.setAttribute("data-lang","{langs[0]}");'
            f'document.documentElement.setAttribute("data-band","{cfg.band}");</script>'
            + head + body)


if __name__ == "__main__":
    print(render())
