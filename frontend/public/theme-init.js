// Runs before first paint (a blocking external script; CSP forbids inline ones) so the page never flashes the wrong theme.
(function () {
  var choice = null;
  try {
    choice = localStorage.getItem('nexus.theme');
  } catch (e) {
    choice = null;
  }
  var light = choice === 'light' || (choice !== 'dark' && matchMedia('(prefers-color-scheme: light)').matches);
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
})();
