(function() {
  var STORAGE_KEY = 'codegraph-theme';
  var html = document.documentElement;
  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || 'dark';
  }
  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }
  setTheme(getTheme());
  var btn = document.getElementById('themeToggle');
  if (!btn) return;
  btn.addEventListener('click', function() {
    var next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next);
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
  });
})();
