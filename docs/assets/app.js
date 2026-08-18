// Daily News for Kids — reading preferences, stored per device.
//
// Two kinds of setting exist and only one of them lives here. Language, theme,
// which beats and regions to show, and how many stories to show act on the page
// immediately and are saved in this browser. Everything that decides how the
// news is written happens when the edition is generated, so this file never
// pretends to change it.
(function () {
  'use strict';

  var root = document.documentElement;
  var KEY = 'dnfk.prefs.v1';

  function readJSON(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
  }

  var CAT = readJSON('prefs-catalogue', null);
  var STR = readJSON('prefs-strings', {});

  function store(value) {
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function defaults() {
    return {
      lang: CAT ? CAT.defaultLang : 'en',
      theme: 'system',
      beats: CAT ? Object.keys(CAT.beats) : [],
      regions: CAT ? Object.keys(CAT.regions).concat(['GLOBAL']) : [],
      count: CAT ? CAT.maxStories : 10
    };
  }

  var prefs = load() || defaults();
  var firstVisit = !load();

  // ---------------------------------------------------------------- applying

  function applyLanguage(lang) {
    root.setAttribute('data-lang', lang);
    document.querySelectorAll('[data-lang-set]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.getAttribute('data-lang-set') === lang));
    });
  }

  function applyTheme(theme) {
    if (theme === 'light' || theme === 'dark') root.setAttribute('data-theme', theme);
    else root.removeAttribute('data-theme');
  }

  function applyFilters() {
    var stories = Array.prototype.slice.call(document.querySelectorAll('.story[data-beat]'));
    if (!stories.length) return;
    var shown = 0;
    stories.forEach(function (el) {
      var beat = el.getAttribute('data-beat');
      var region = el.getAttribute('data-region');
      // A story with a beat or region the catalogue does not know — an archived
      // edition from before a rename — stays visible rather than vanishing.
      var beatOk = !CAT || !(beat in CAT.beats) || prefs.beats.indexOf(beat) !== -1;
      var regionOk = !CAT || (region !== 'GLOBAL' && !(region in CAT.regions))
        || prefs.regions.indexOf(region) !== -1;
      var visible = beatOk && regionOk && shown < prefs.count;
      if (visible) shown++;
      el.hidden = !visible;
    });
    var notice = document.querySelector('.no-match');
    if (notice) notice.hidden = shown > 0;
  }

  function applyAll() {
    applyLanguage(prefs.lang);
    applyTheme(prefs.theme);
    applyFilters();
  }

  applyAll();

  // ------------------------------------------------------------------ dialog

  var dialog = document.getElementById('settings');

  function text(key) {
    var entry = STR[key] || {};
    return entry[prefs.lang] || entry.en || '';
  }

  function segment(container, options, current, onPick) {
    if (!container) return;
    container.innerHTML = '';
    options.forEach(function (opt) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = opt.label;
      b.setAttribute('aria-pressed', String(opt.value === current));
      b.addEventListener('click', function () {
        onPick(opt.value);
        Array.prototype.forEach.call(container.children, function (c) {
          c.setAttribute('aria-pressed', String(c === b));
        });
      });
      container.appendChild(b);
    });
  }

  function chips(container, entries, selected, onToggle) {
    if (!container) return;
    container.innerHTML = '';
    Object.keys(entries).forEach(function (key) {
      var entry = entries[key];
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip-toggle';
      b.dataset.key = key;
      if (entry.color) b.style.setProperty('--dot', entry.color);
      var label = entry.label[prefs.lang] || entry.label.en;
      if (entry.color) {
        var dot = document.createElement('span');
        dot.className = 'dot';
        b.appendChild(dot);
      }
      b.appendChild(document.createTextNode(label));
      b.setAttribute('aria-pressed', String(selected.indexOf(key) !== -1));
      b.addEventListener('click', function () {
        var on = b.getAttribute('aria-pressed') !== 'true';
        b.setAttribute('aria-pressed', String(on));
        onToggle(key, on);
      });
      container.appendChild(b);
    });
  }

  var draft = null;

  function buildDialog() {
    if (!dialog || !CAT) return;
    draft = JSON.parse(JSON.stringify(prefs));

    segment(document.getElementById('prefLang'),
      CAT.languages.map(function (l) { return { value: l.code, label: l.label }; }),
      draft.lang, function (v) { draft.lang = v; applyLanguage(v); rebuildLabels(); });

    segment(document.getElementById('prefTheme'), [
      { value: 'system', label: text('theme_system') },
      { value: 'light', label: text('theme_light') },
      { value: 'dark', label: text('theme_dark') }
    ], draft.theme, function (v) { draft.theme = v; applyTheme(v); });

    chips(document.getElementById('prefBeats'), CAT.beats, draft.beats, function (key, on) {
      toggleIn(draft.beats, key, on);
    });
    var regionEntries = {};
    Object.keys(CAT.regions).forEach(function (k) { regionEntries[k] = CAT.regions[k]; });
    regionEntries.GLOBAL = { label: { en: 'Global', zh: '全球' } };
    chips(document.getElementById('prefRegions'), regionEntries, draft.regions, function (key, on) {
      toggleIn(draft.regions, key, on);
    });

    var range = document.getElementById('prefCount');
    var out = document.getElementById('prefCountOut');
    if (range) {
      range.value = draft.count;
      if (out) out.textContent = draft.count;
      range.oninput = function () {
        draft.count = Number(range.value);
        if (out) out.textContent = draft.count;
      };
    }

    var welcome = document.getElementById('mWelcome');
    if (welcome) welcome.hidden = !firstVisit;
  }

  function rebuildLabels() {
    // Language changed inside the dialog: redraw the parts whose text is in JS.
    var savedDraft = draft;
    buildDialog();
    draft = savedDraft;
  }

  function toggleIn(list, key, on) {
    var i = list.indexOf(key);
    if (on && i === -1) list.push(key);
    if (!on && i !== -1) list.splice(i, 1);
  }

  function openDialog() {
    buildDialog();
    if (!dialog) return;
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  function closeDialog() {
    if (!dialog) return;
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }

  document.addEventListener('click', function (ev) {
    if (ev.target.closest('[data-open-settings]')) { openDialog(); return; }

    var bulk = ev.target.closest('[data-bulk]');
    if (bulk && draft) {
      var which = bulk.getAttribute('data-bulk');
      var on = bulk.getAttribute('data-on') === '1';
      var container = document.getElementById(which === 'beats' ? 'prefBeats' : 'prefRegions');
      var list = which === 'beats' ? draft.beats : draft.regions;
      list.length = 0;
      Array.prototype.forEach.call(container.children, function (c) {
        c.setAttribute('aria-pressed', String(on));
        if (on) list.push(c.dataset.key);
      });
      return;
    }

    if (ev.target.closest('#prefSave')) {
      // An empty filter would show an empty paper; treat it as "everything".
      if (!draft.beats.length) draft.beats = Object.keys(CAT.beats);
      if (!draft.regions.length) draft.regions = Object.keys(CAT.regions).concat(['GLOBAL']);
      prefs = draft;
      store(prefs);
      firstVisit = false;
      applyAll();
      var status = document.getElementById('prefStatus');
      if (status) {
        status.textContent = text('saved');
        setTimeout(function () { status.textContent = ''; }, 1800);
      }
      setTimeout(closeDialog, 350);
      return;
    }

    if (ev.target.closest('#prefReset')) {
      prefs = defaults();
      store(prefs);
      applyAll();
      buildDialog();
      return;
    }

    // The header buttons still work for people who never open the dialog.
    var langBtn = ev.target.closest('[data-lang-set]');
    if (langBtn) {
      prefs.lang = langBtn.getAttribute('data-lang-set');
      store(prefs);
      applyLanguage(prefs.lang);
      return;
    }

    if (ev.target.closest('[data-theme-toggle]')) {
      var current = root.getAttribute('data-theme');
      if (!current) {
        current = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      prefs.theme = current === 'dark' ? 'light' : 'dark';
      store(prefs);
      applyTheme(prefs.theme);
    }
  });

  // Clicking the backdrop closes without saving.
  if (dialog) {
    dialog.addEventListener('click', function (ev) {
      if (ev.target === dialog) closeDialog();
    });
    dialog.addEventListener('close', function () {
      // Anything not saved is discarded, so put the page back how it was.
      applyAll();
    });
  }

  // First visit on this device: ask before showing the paper.
  if (firstVisit && dialog) {
    store(prefs);          // so a refresh mid-setup does not ask again forever
    firstVisit = true;
    openDialog();
  }
})();
