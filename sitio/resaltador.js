/* resaltador.js — «resaltar términos» en la lectura de una obra.
   Cuatro categorías, de lo que declaró la autora (terminos.json, lo arma
   terminos.py): glosario, nodos, instrumentos y lemas diferenciados. Cada
   una se prende y se apaga desde el panel de lectura; el término lleva un
   subrayado de color y, al pasar el mouse, de dónde viene.

   La página lo usa así (obra-template.html):
     RESALTAR.pintar(elementoDelTexto)   después de cada capítulo
     RESALTAR.panel(elementoDelPanel)    arma los botones en «lectura» */
(function () {
  'use strict';
  const yo = document.currentScript;
  const BASE = new URL('.', yo ? yo.src : location.href).href;
  const CATS = [
    ['glosario', 'glosario'],
    ['nodos', 'nodos'],
    ['instrumentos', 'instrumentos'],
    ['lemas', 'lemas diferenciados'],
  ];
  const CLAVE = 'p314b_resaltar';
  let activas = {};
  try { activas = JSON.parse(localStorage.getItem(CLAVE) || '{}') || {}; } catch (e) { activas = {}; }
  let datos = null, palabras = null, frases = null;

  const css = document.createElement('style');
  css.textContent = `
:root { --rt-glosario: #a78bfa; --rt-nodos: #34d399; --rt-instrumentos: #f59e0b; --rt-lemas: #60a5fa; }
.rt { text-decoration: none; }
body.rt-glosario .rt[data-c~="glosario"],
body.rt-nodos .rt[data-c~="nodos"],
body.rt-instrumentos .rt[data-c~="instrumentos"],
body.rt-lemas .rt[data-c~="lemas"] { text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 3px; cursor: help; }
body.rt-lemas .rt[data-c~="lemas"] { text-decoration-color: var(--rt-lemas); }
body.rt-nodos .rt[data-c~="nodos"] { text-decoration-color: var(--rt-nodos); }
body.rt-instrumentos .rt[data-c~="instrumentos"] { text-decoration-color: var(--rt-instrumentos); }
body.rt-glosario .rt[data-c~="glosario"] { text-decoration-color: var(--rt-glosario); }
.rt-ops { display: flex; flex-wrap: wrap; gap: 6px; }
.rt-op { font-family: var(--font-mono); font-size: 10.5px; padding: 5px 9px; border: 1px solid var(--rule); border-radius: 999px; background: transparent; color: var(--ink-soft); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.rt-op i { width: 9px; height: 3px; border-radius: 2px; display: inline-block; }
.rt-op[aria-pressed="true"] { color: var(--ink); border-color: currentColor; }
.rt-tit { font-family: var(--font-mono); font-size: 9.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-muted); margin: 14px 0 8px; }
`;
  document.head.appendChild(css);

  function aplicarClases() {
    CATS.forEach(([k]) => document.body.classList.toggle('rt-' + k, !!activas[k]));
  }
  const esc = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  async function cargar() {
    if (datos) return datos;
    try { const r = await fetch(BASE + 'terminos.json', { cache: 'no-store' }); datos = r.ok ? await r.json() : {}; }
    catch (e) { datos = {}; }
    // una palabra (con guiones incluidos) se busca por token; lo de varias
    // palabras, como frase dentro de un mismo texto
    palabras = new Map(); frases = [];
    CATS.forEach(([cat]) => (datos[cat] || []).forEach(x => {
      const t = String(x.t || '').trim(); if (!t) return;
      const e = { cat, etiqueta: x.e || cat, exacto: !!x.exacto };
      if (/\s/.test(t)) frases.push(Object.assign({ t }, e));
      else {
        const k = e.exacto ? t : t.toLowerCase();
        if (!palabras.has(k)) palabras.set(k, []);
        palabras.get(k).push(e);
      }
    }));
    frases.sort((a, b) => b.t.length - a.t.length);
    return datos;
  }
  function envolver(texto, info) {
    const s = document.createElement('span');
    s.className = 'rt';
    s.dataset.c = [...new Set(info.map(i => i.cat))].join(' ');
    s.title = [...new Set(info.map(i => i.etiqueta))].join(' · ');
    s.textContent = texto;
    return s;
  }
  // Recorre los nodos de texto sin tocar fórmulas, homófonos ni lo ya marcado.
  function pintarNodo(n) {
    const v = n.nodeValue;
    if (!v || !/[\p{L}]/u.test(v)) return;
    const frag = document.createDocumentFragment();
    let resto = v, cambio = false;
    // frases primero
    const hallazgos = [];
    frases.forEach(f => {
      const rx = new RegExp('(^|[^\\p{L}])(' + esc(f.t).replace(/ /g, '\\s+') + ')(?=[^\\p{L}]|$)', f.exacto ? 'gu' : 'giu');
      let m; while ((m = rx.exec(v))) hallazgos.push([m.index + m[1].length, m.index + m[1].length + m[2].length, [f]]);
    });
    // palabras
    const rxp = /[\p{L}][\p{L}\-]*/gu; let m;
    while ((m = rxp.exec(v))) {
      const w = m[0], info = (palabras.get(w) || []).concat(w !== w.toLowerCase() ? (palabras.get(w.toLowerCase()) || []).filter(i => !i.exacto) : []);
      if (info.length) hallazgos.push([m.index, m.index + w.length, info]);
    }
    if (!hallazgos.length) return;
    hallazgos.sort((a, b) => a[0] - b[0] || (b[1] - b[0]) - (a[1] - a[0]));
    let pos = 0;
    hallazgos.forEach(([a, b, info]) => {
      if (a < pos) return; // se superpone con uno anterior (más largo)
      if (a > pos) frag.appendChild(document.createTextNode(v.slice(pos, a)));
      frag.appendChild(envolver(v.slice(a, b), info));
      pos = b; cambio = true;
    });
    if (!cambio) return;
    if (pos < v.length) frag.appendChild(document.createTextNode(v.slice(pos)));
    n.replaceWith(frag);
  }
  // Con los términos ya cargados corre en el acto (antes que los demás
  // efectos de lectura, que parten el texto en pedazos); la primera vez,
  // cuando llegan.
  function pintar(cont) {
    if (!cont) return;
    aplicarClases();
    if (!CATS.some(([k]) => activas[k])) return; // nada prendido: no se toca el texto
    if (!palabras) { cargar().then(() => pintarYa(cont)); return; }
    pintarYa(cont);
  }
  function pintarYa(cont) {
    if (cont.querySelector('.rt') || cont.dataset.rtVacio === cont.textContent.length + '') return;
    const w = document.createTreeWalker(cont, NodeFilter.SHOW_TEXT, {
      acceptNode: n => n.parentNode.closest('.rt, .katex, .homo, script, style, code') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodos = []; let n; while ((n = w.nextNode())) nodos.push(n);
    nodos.forEach(pintarNodo);
    if (!cont.querySelector('.rt')) cont.dataset.rtVacio = cont.textContent.length + '';
  }
  let elPanel = null, avisar = null;
  function panel(el, alCambiar) {
    if (!el) return;
    elPanel = el; avisar = alCambiar;
    el.innerHTML = '<div class="rt-tit">resaltar términos</div><div class="rt-ops">'
      + CATS.map(([k, t]) => `<button class="rt-op" data-rt="${k}" aria-pressed="${!!activas[k]}"><i style="background:var(--rt-${k})"></i>${t}</button>`).join('') + '</div>';
    el.querySelectorAll('[data-rt]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      activas[b.dataset.rt] = !activas[b.dataset.rt];
      try { localStorage.setItem(CLAVE, JSON.stringify(activas)); } catch (er) {}
      b.setAttribute('aria-pressed', String(!!activas[b.dataset.rt]));
      aplicarClases();
      if (typeof alCambiar === 'function') alCambiar();
    }));
  }
  // Lo usan las intenciones del panel de lectura: deja prendidas solo las
  // categorías que vienen en «cuales» ({ glosario: true, … }).
  function fijar(cuales) {
    activas = {};
    CATS.forEach(([k]) => { if (cuales && cuales[k]) activas[k] = true; });
    try { localStorage.setItem(CLAVE, JSON.stringify(activas)); } catch (er) {}
    if (elPanel) panel(elPanel, avisar);
    aplicarClases();
    if (typeof avisar === 'function') avisar();
  }
  const estado = () => Object.assign({}, activas);
  if (CATS.some(([k]) => activas[k])) cargar();
  window.RESALTAR = { pintar, panel, fijar, estado };
})();
