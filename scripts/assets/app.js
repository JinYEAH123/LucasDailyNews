// Daily News for Kids — reading level, language and theme, stored per device.
//
// The age band is the only control that changes the words on the page, and it
// works because all three bands are already in the HTML: switching is one
// attribute on the root element. Nothing here talks to a server, and nothing
// here pretends to change what tomorrow's edition will say.
(function () {
  'use strict';

  var root = document.documentElement;
  var KEY = 'dnfk.v3';

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
  }

  function save(prefs) {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* private mode */ }
  }

  var prefs = load();

  function pressed(selector, attr, value) {
    document.querySelectorAll(selector).forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.getAttribute(attr) === value));
    });
  }

  function applyBand(band) {
    if (!band) return;
    root.setAttribute('data-band', band);
    pressed('[data-band-set]', 'data-band-set', band);
  }

  function applyLang(lang) {
    if (!lang) return;
    root.setAttribute('data-lang', lang);
    pressed('[data-lang-set]', 'data-lang-set', lang);
  }

  function applyTheme(theme) {
    if (theme === 'light' || theme === 'dark') root.setAttribute('data-theme', theme);
    else root.removeAttribute('data-theme');
  }

  // A stored choice wins; otherwise the page keeps the default the site was
  // built with, which already sits on the root element.
  applyBand(prefs.band || root.getAttribute('data-band'));
  applyLang(prefs.lang || root.getAttribute('data-lang'));
  if (prefs.theme) applyTheme(prefs.theme);

  document.addEventListener('click', function (ev) {
    var band = ev.target.closest('[data-band-set]');
    if (band) {
      prefs.band = band.getAttribute('data-band-set');
      save(prefs);
      applyBand(prefs.band);
      return;
    }

    var lang = ev.target.closest('[data-lang-set]');
    if (lang) {
      prefs.lang = lang.getAttribute('data-lang-set');
      save(prefs);
      applyLang(prefs.lang);
      return;
    }

    if (ev.target.closest('[data-theme-toggle]')) {
      var current = root.getAttribute('data-theme');
      if (!current) {
        current = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      prefs.theme = current === 'dark' ? 'light' : 'dark';
      save(prefs);
      applyTheme(prefs.theme);
    }
  });
})();
