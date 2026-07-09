(function () {
  const LOADER_KEY = 'nav-pending';
  const loader = document.getElementById('page-loader');

  function showLoader() {
    document.documentElement.classList.add('nav-loading');
    document.body.classList.add('is-navigating');
    if (loader) loader.setAttribute('aria-hidden', 'false');
  }

  function hideLoader() {
    document.documentElement.classList.remove('nav-loading');
    document.body.classList.remove('is-navigating');
    if (loader) loader.setAttribute('aria-hidden', 'true');
    try {
      sessionStorage.removeItem(LOADER_KEY);
    } catch (e) {
      /* ignore */
    }
  }

  function isInternalPageNav(anchor) {
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:'))
      return false;
    if (anchor.hasAttribute('download')) return false;
    if (anchor.classList.contains('page-link-ajax')) return false;
    if (anchor.classList.contains('nav-cta')) return false;
    if (href.startsWith('/api/')) return false;
    if (anchor.target && anchor.target !== '_self') return false;
    try {
      const url = new URL(href, window.location.origin);
      return url.origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  function markNavActive(anchor) {
    const navItem = anchor.closest('.idbi-nav a');
    if (!navItem || navItem.classList.contains('nav-cta') || navItem.classList.contains('nav-logout'))
      return;
    document.querySelectorAll('.idbi-nav a.active').forEach((a) => a.classList.remove('active'));
    navItem.classList.add('active');
  }

  function beginNavigation(anchor) {
    markNavActive(anchor);
    try {
      sessionStorage.setItem(LOADER_KEY, '1');
    } catch (e) {
      /* ignore */
    }
    showLoader();
  }

  if (!sessionStorage.getItem(LOADER_KEY)) {
    hideLoader();
  }

  window.addEventListener('pageshow', hideLoader);

  document.addEventListener(
    'click',
    (event) => {
      const anchor = event.target.closest('a[href]');
      if (!anchor || !isInternalPageNav(anchor)) return;
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      beginNavigation(anchor);
    },
    true
  );

  document.querySelectorAll('form.login-form').forEach((form) => {
    form.addEventListener('submit', () => {
      try {
        sessionStorage.setItem(LOADER_KEY, '1');
      } catch (e) {
        /* ignore */
      }
      showLoader();
    });
  });
})();
