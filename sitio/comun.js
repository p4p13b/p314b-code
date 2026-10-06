/* comun.js — piezas que comparten las páginas y los módulos del sitio.
   Va antes que los demás scripts (en las obras: ../comun.js).
   P314.esc(s): texto a HTML seguro, sin null/undefined y con las comillas
   escapadas (sirve en texto y en atributos). */
(function () {
  'use strict';
  var MAPA = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  window.P314 = window.P314 || {};
  window.P314.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return MAPA[c]; });
  };
})();
