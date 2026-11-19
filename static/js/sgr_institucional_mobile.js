/* Menú móvil accesible. No modifica formularios ni rutas. */
(() => {
  'use strict';
  const sidebar = document.getElementById('sgr-sidebar-navigation');
  const toggle = document.getElementById('sgr-menu-toggle');
  const close = document.getElementById('sgr-menu-close');
  const backdrop = document.getElementById('sgr-mobile-backdrop');
  if (!sidebar || !toggle || !close || !backdrop) return;
  const isMobile = () => window.matchMedia('(max-width: 991.98px)').matches;
  const setOpen = (open, moveFocus = true) => {
    const enabled = Boolean(open && isMobile());
    document.body.classList.toggle('sgr-nav-open', enabled);
    toggle.setAttribute('aria-expanded', String(enabled));
    sidebar.setAttribute('aria-hidden', String(!enabled && isMobile()));
    sidebar.inert = !enabled && isMobile();
    if (moveFocus) (enabled ? close : toggle).focus();
  };
  toggle.addEventListener('click', () => setOpen(!document.body.classList.contains('sgr-nav-open')));
  close.addEventListener('click', () => setOpen(false));
  backdrop.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('sgr-nav-open')) setOpen(false);
  });
  sidebar.querySelectorAll('a[href]').forEach(link => {
    link.addEventListener('click', () => { if (isMobile()) setOpen(false, false); });
  });
  const onResize = () => {
    if (!isMobile()) {
      document.body.classList.remove('sgr-nav-open');
      toggle.setAttribute('aria-expanded', 'false');
      sidebar.removeAttribute('aria-hidden');
      sidebar.inert = false;
    } else {
      sidebar.setAttribute('aria-hidden', String(!document.body.classList.contains('sgr-nav-open')));
      sidebar.inert = !document.body.classList.contains('sgr-nav-open');
    }
  };
  window.addEventListener('resize', onResize);
  onResize();
})();
