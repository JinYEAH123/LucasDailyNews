// Lucas Daily News — language + theme toggles, persisted in localStorage.
(function () {
  var root = document.documentElement;

  function apply(key, value, attr) {
    root.setAttribute(attr, value);
    try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
    document.querySelectorAll('[data-' + key + '-set]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.getAttribute('data-' + key + '-set') === value));
    });
  }

  // Language: default English (Lucas reads it at school); 中文 for reading along.
  var lang = 'en';
  try { lang = localStorage.getItem('lang') || 'en'; } catch (e) {}
  apply('lang', lang, 'data-lang');

  // Theme: default follows the device until the reader picks one.
  var theme = null;
  try { theme = localStorage.getItem('theme'); } catch (e) {}
  if (theme) root.setAttribute('data-theme', theme);

  document.addEventListener('click', function (ev) {
    var el = ev.target.closest('[data-lang-set]');
    if (el) { apply('lang', el.getAttribute('data-lang-set'), 'data-lang'); return; }

    if (ev.target.closest('[data-theme-toggle]')) {
      var current = root.getAttribute('data-theme');
      if (!current) {
        current = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      var next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    }
  });
})();
