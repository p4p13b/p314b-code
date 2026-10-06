/* visita.js — avisa que alguien abrió esta página (contador de la autora,
   worker/huella.js → /api/visita). Manda solo la ruta y el dominio de donde
   vino; nada de quién es. No cuenta a la autora (con su token en este
   navegador), ni lo que se abre al costado, ni en local.
   De paso carga comentar.js (el cuadro para comentar), en todas. */
(function () {
  'use strict';
  // de paso, el cuadro para comentar en cualquier parte (comentar.js, al lado)
  try {
    const c = document.createElement('script');
    c.src = new URL('comentar.js', document.currentScript.src).href;
    document.head.appendChild(c);
  } catch (e) {}
  try {
    if (document.documentElement.classList.contains('en-panel') || window.top !== window) return;
    if (/^(localhost|127\.0\.0\.1|\[::1\]|)$/.test(location.hostname) || location.protocol === 'file:') return;
    if (localStorage.getItem('p314b_gh_token')) return;
    const datos = JSON.stringify({ p: location.pathname, r: document.referrer || '' });
    if (navigator.sendBeacon) navigator.sendBeacon('/api/visita', new Blob([datos], { type: 'application/json' }));
  } catch (e) {}
})();
