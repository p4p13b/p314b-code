/* lectura-extra.js — otras lecturas de un texto (opciones del panel ⚙ lectura).

   · oír mal a propósito (homofonía forzada): toda forma de homofonos.json se
     lee como su par (de sí → decí, a la → ala), no solo las que la autora
     marcó. La original queda al pasar el mouse.
   · sismógrafo: una franja al costado sube donde el texto se espesa (palabras
     raras en el corpus y términos de terminos.json) y baja en las
     transiciones. Marca por dónde va la lectura; tocarla lleva ahí.
   · partitura: el texto suena desde el párrafo en pantalla. Cada palabra es
     una nota: más aguda cuanto más rara en el corpus (partitura.json), más
     larga cuanto más larga es; la puntuación son silencios, los términos un
     acorde.
   · parientes: tocar una palabra muestra su familia (las subfamilias que el
     uso une o separa) y su genealogía: en qué textos aparece cada miembro,
     por fecha de escritura (parientes.json, de parientes.py).
   · mismizar: un botón ∞ junto a cada párrafo lo recompone con los
     parientes de sus palabras; lo que no tiene familia se va borrando y, en
     seis pasos, cada palabra queda en la forma más usada de su familia: el
     párrafo se fija en una figura que se repite (siempre la misma para ese
     párrafo) y se queda quieto. Tocar ∞ de nuevo lo devuelve.
   · huella: se anota, solo en este navegador, qué partes se leyeron, cuánto
     tiempo y en qué orden (huella.html la muestra).

   La página lo usa así (obra-template.html):
     EXTRA.pintar(texto)            después de cada capítulo
     EXTRA.panel(el, rehacer)       arma los botones en «lectura»
     EXTRA.paso(slug, idx, titulo)  al abrir un capítulo (huella) */
(function () {
  'use strict';
  const yo = document.currentScript;
  const BASE = new URL('.', yo ? yo.src : location.href).href;
  const CLAVE = 'p314b_extra';
  let op = {};
  try { op = JSON.parse(localStorage.getItem(CLAVE) || '{}') || {}; } catch (e) { op = {}; }
  const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(op)); } catch (e) {} };
  const quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const json = (f) => fetch(BASE + f, { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).catch(() => null);
  const memo = {};
  const datos = f => memo[f] || (memo[f] = json(f));
  const LETRA = /[\p{L}][\p{L}\-]*/gu;

  const css = document.createElement('style');
  css.textContent = `
.hf { text-decoration: underline dotted var(--violet, #a78bfa) 1.5px; text-underline-offset: .28em; cursor: help; }
.ex-tit { font-family: var(--font-mono); font-size: 9.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-muted); margin: 14px 0 8px; }
.ex-ops { display: flex; flex-wrap: wrap; gap: 6px; }
.ex-op { font-family: var(--font-mono); font-size: 10.5px; padding: 5px 9px; border: 1px solid var(--rule); border-radius: 999px; background: transparent; color: var(--ink-soft); cursor: pointer; text-decoration: none; }
.ex-op[aria-pressed="true"] { color: var(--ink); border-color: currentColor; }
.sismo { position: fixed; right: 0; top: 64px; height: calc(100vh - 64px); width: 34px; z-index: 60; cursor: pointer; opacity: .85; }
.sismo:hover { opacity: 1; }
@media (max-width: 700px) { .sismo { width: 22px; } }
::highlight(partitura) { background: var(--violet-bg-p, rgba(167,139,250,.3)); color: inherit; }
.parti-sonando { box-shadow: inset 3px 0 0 var(--violet, #a78bfa); }
body.ex-parientes #text-body { cursor: help; }
.par-card { position: fixed; z-index: 9500; width: min(420px, calc(100vw - 24px)); max-height: min(70vh, 560px); overflow: auto; background: var(--page, #111); color: var(--ink, #eee); border: 1px solid var(--rule, #333); border-left: 2px solid var(--violet, #a78bfa); border-radius: 4px; padding: 14px 16px; box-shadow: 0 16px 40px rgba(0,0,0,.45); font-family: var(--font-mono); font-size: 12px; line-height: 1.5; }
.par-card h4 { margin: 0 0 2px; font-family: var(--font-body, serif); font-style: italic; font-weight: 400; font-size: 20px; }
.par-card .par-sub { color: var(--ink-muted); font-size: 10.5px; letter-spacing: .08em; margin-bottom: 10px; }
.par-card .par-x { position: absolute; top: 8px; right: 10px; background: none; border: 0; color: var(--ink-muted); cursor: pointer; font: inherit; font-size: 16px; }
.par-grupo { display: flex; flex-wrap: wrap; gap: 5px; }
.par-grupo span { border: 1px solid var(--rule); border-radius: 999px; padding: 2px 8px; }
.par-grupo span.yo { border-color: var(--violet, #a78bfa); color: var(--ink); }
.par-sep { color: var(--ink-muted); font-size: 10px; margin: 6px 0; letter-spacing: .06em; }
.par-card svg { display: block; width: 100%; height: auto; margin-top: 12px; }
.par-card svg text { fill: var(--ink-muted); font-size: 9px; font-family: var(--font-mono); }
.par-card svg .pg { fill: var(--violet, #a78bfa); cursor: pointer; }
.par-card svg .pg.yo { fill: var(--ink, #eee); }
.par-card .par-nota { color: var(--ink-muted); font-size: 10.5px; margin-top: 8px; }
.mz-btn { position: absolute; z-index: 45; width: 26px; height: 26px; border-radius: 50%; border: 1px solid var(--rule); background: var(--page, #111); color: var(--ink-muted); cursor: pointer; font-size: 15px; line-height: 1; display: none; padding: 0; }
.mz-btn:hover, .mz-btn.activo { color: var(--violet, #a78bfa); border-color: currentColor; }
.mz { transition: opacity .6s; }
.mz-fijo { border-left: 1px dotted var(--violet, #a78bfa); padding-left: .7em; margin-left: -.7em; }
`;
  document.head.appendChild(css);

  /* ── homofonía forzada ── */
  let hfMapa = null, hfRx = null;
  async function cargarHomofonos() {
    if (hfMapa) return;
    const d = await datos('homofonos.json');
    hfMapa = new Map();
    ((d && d.grupos) || []).forEach(g => {
      // cada forma se lee como la siguiente del grupo (en ronda); las que
      // solo cambian mayúsculas (Nadie / nadie) no cuentan
      const formas = [];
      g.forEach(w => { const k = String(w).toLowerCase().replace(/\s+/g, ' ').trim(); if (k && !formas.some(f => f.k === k)) formas.push({ k, w: String(w).trim() }); });
      if (formas.length < 2) return;
      formas.forEach((f, i) => { if (!hfMapa.has(f.k)) hfMapa.set(f.k, formas[(i + 1) % formas.length].w); });
    });
    const claves = [...hfMapa.keys()].sort((a, b) => b.length - a.length)
      .map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+'));
    hfRx = claves.length ? new RegExp('(^|[^\\p{L}])(' + claves.join('|') + ')(?=[^\\p{L}]|$)', 'giu') : null;
  }
  function conMayuscula(modelo, w) {
    return modelo[0] && modelo[0] !== modelo[0].toLowerCase() ? w[0].toUpperCase() + w.slice(1) : w;
  }
  function forzar(cont) {
    if (!hfRx || cont.querySelector('.hf')) return;
    const w = document.createTreeWalker(cont, NodeFilter.SHOW_TEXT, {
      acceptNode: n => n.parentNode.closest('.hf, .homo, .katex, script, style, code') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodos = []; let n; while ((n = w.nextNode())) nodos.push(n);
    nodos.forEach(n => {
      const v = n.nodeValue; hfRx.lastIndex = 0;
      let m, pos = 0; const frag = document.createDocumentFragment();
      while ((m = hfRx.exec(v))) {
        const a = m.index + m[1].length, orig = m[2];
        const otra = hfMapa.get(orig.toLowerCase().replace(/\s+/g, ' '));
        if (!otra) continue;
        if (a > pos) frag.appendChild(document.createTextNode(v.slice(pos, a)));
        const s = document.createElement('span');
        s.className = 'hf'; s.title = 'dice: ' + orig; s.textContent = conMayuscula(orig, otra);
        frag.appendChild(s);
        pos = a + orig.length;
      }
      if (!pos) return;
      if (pos < v.length) frag.appendChild(document.createTextNode(v.slice(pos)));
      n.replaceWith(frag);
    });
  }

  /* ── rareza y términos (partitura y sismógrafo) ── */
  let bandas = null, terminos = null;
  async function cargarRareza() {
    if (bandas) return;
    const [p, t] = await Promise.all([datos('partitura.json'), datos('terminos.json')]);
    bandas = (p && p.b) || {};
    terminos = new Set();
    ['glosario', 'nodos', 'instrumentos', 'lemas'].forEach(c => ((t && t[c]) || []).forEach(x => {
      const k = String(x.t || '').toLowerCase().trim(); if (k && !/\s/.test(k)) terminos.add(k);
    }));
  }
  const banda = w => { const b = bandas[w.toLowerCase()]; return b == null ? 12 : b; };

  /* ── sismógrafo ── */
  let sismo = null, sismoCont = null, sismoPars = [], sismoPend = false;
  function bloques(cont) {
    return [...cont.querySelectorAll('p, li, blockquote, h2, h3, h4')].filter(p => !p.querySelector('p, li') && p.textContent.trim());
  }
  function medir(cont) {
    return bloques(cont).map(el => {
      const ws = el.textContent.match(LETRA) || [];
      if (!ws.length) return { el, v: 0 };
      let s = 0;
      ws.forEach(w => { const b = banda(w); s += b >= 9 ? (b - 8) / 4 : 0; if (terminos.has(w.toLowerCase())) s += 1.5; });
      return { el, v: s / Math.sqrt(ws.length) };
    });
  }
  function dibujarSismo() {
    sismoPend = false;
    if (!sismo || !sismoCont) return;
    const dpr = devicePixelRatio || 1, W = sismo.clientWidth, H = sismo.clientHeight;
    sismo.width = W * dpr; sismo.height = H * dpr;
    const g = sismo.getContext('2d'); g.scale(dpr, dpr); g.clearRect(0, 0, W, H);
    if (!sismoPars.length) return;
    const top0 = sismoCont.getBoundingClientRect().top + scrollY, alto = Math.max(1, sismoCont.scrollHeight);
    const max = Math.max(...sismoPars.map(p => p.v), 0.01);
    const cs = getComputedStyle(document.documentElement);
    const tinta = cs.getPropertyValue('--ink-muted').trim() || '#888', viol = cs.getPropertyValue('--violet').trim() || '#a78bfa';
    // línea base y trazo
    g.strokeStyle = tinta; g.globalAlpha = .25; g.beginPath(); g.moveTo(4, 0); g.lineTo(4, H); g.stroke(); g.globalAlpha = 1;
    g.strokeStyle = viol; g.lineWidth = 1.4; g.beginPath();
    sismoPars.forEach((p, i) => {
      const r = p.el.getBoundingClientRect();
      const y0 = ((r.top + scrollY - top0) / alto) * H, y1 = ((r.bottom + scrollY - top0) / alto) * H;
      const x = 4 + (p.v / max) * (W - 8);
      if (i === 0) g.moveTo(4, y0);
      // un temblor dentro del párrafo, proporcional a su densidad
      const pasos = Math.max(2, Math.round((y1 - y0) / 3));
      for (let k = 0; k <= pasos; k++) {
        const y = y0 + (y1 - y0) * k / pasos;
        const j = quieto ? 0 : Math.sin(k * 2.3 + i) * (p.v / max) * 2.5;
        g.lineTo(Math.max(4, x + j - (k % 2) * (p.v / max) * 3), y);
      }
    });
    g.stroke();
    // por dónde va la lectura
    const yLee = ((scrollY + innerHeight / 3 - top0) / alto) * H;
    g.fillStyle = tinta; g.globalAlpha = .9; g.fillRect(0, Math.max(0, Math.min(H - 2, yLee)), W, 2); g.globalAlpha = 1;
  }
  function sismografo(cont) {
    if (!op.sismo) { if (sismo) { sismo.remove(); sismo = null; } return; }
    if (!sismo) {
      sismo = document.createElement('canvas');
      sismo.className = 'sismo';
      sismo.title = 'sismógrafo: dónde se espesa el texto (tocar para ir)';
      sismo.addEventListener('click', e => {
        if (!sismoCont) return;
        const r = sismo.getBoundingClientRect(), f = (e.clientY - r.top) / r.height;
        const top0 = sismoCont.getBoundingClientRect().top + scrollY;
        scrollTo({ top: top0 + f * sismoCont.scrollHeight - innerHeight / 3, behavior: quieto ? 'auto' : 'smooth' });
      });
      document.body.appendChild(sismo);
      const pedir = () => { if (!sismoPend) { sismoPend = true; requestAnimationFrame(dibujarSismo); } };
      addEventListener('scroll', pedir, { passive: true });
      addEventListener('resize', pedir);
    }
    sismoCont = cont;
    cargarRareza().then(() => { sismoPars = medir(cont); dibujarSismo(); });
  }

  /* ── partitura ── */
  const ESCALA = [0, 2, 4, 7, 9]; // pentatónica
  let audio = null, sonando = null;
  function frecuencia(b) {
    const paso = b + 2, oct = Math.floor(paso / ESCALA.length), g = ESCALA[paso % ESCALA.length];
    return 196 * Math.pow(2, oct + g / 12); // desde sol grave
  }
  function nota(t, f, dur, vol, tipo) {
    const o = audio.createOscillator(), v = audio.createGain();
    o.type = tipo || 'sine'; o.frequency.value = f;
    v.gain.setValueAtTime(0, t);
    v.gain.linearRampToValueAtTime(vol, t + 0.012);
    v.gain.exponentialRampToValueAtTime(0.0008, t + dur * 1.6);
    o.connect(v).connect(audio.destination);
    o.start(t); o.stop(t + dur * 1.7);
  }
  function parar() {
    if (!sonando) return;
    sonando.fin = true;
    clearTimeout(sonando.reloj);
    if (window.CSS && CSS.highlights) CSS.highlights.delete('partitura');
    document.querySelectorAll('.parti-sonando').forEach(x => x.classList.remove('parti-sonando'));
    sonando = null;
    pintarBotones();
  }
  async function tocar(cont) {
    if (sonando) { parar(); return; }
    await cargarRareza();
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === 'suspended') await audio.resume();
    const pars = bloques(cont);
    let i = pars.findIndex(p => p.getBoundingClientRect().bottom > innerHeight * 0.2);
    if (i < 0) i = 0;
    sonando = { fin: false };
    pintarBotones();
    const estado = sonando;
    const tocarPar = () => {
      if (estado.fin) return;
      const p = pars[i];
      if (!p) { parar(); return; }
      document.querySelectorAll('.parti-sonando').forEach(x => x.classList.remove('parti-sonando'));
      p.classList.add('parti-sonando');
      if (p.getBoundingClientRect().top > innerHeight * 0.7 || p.getBoundingClientRect().bottom < 0) p.scrollIntoView({ block: 'center', behavior: quieto ? 'auto' : 'smooth' });
      // palabras y signos, con su lugar en los nodos de texto (para resaltar)
      const piezas = [];
      const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) {
        const rx = /([\p{L}][\p{L}\-]*)|([,;:—–])|([.?!…]+)/gu; let m;
        while ((m = rx.exec(n.nodeValue))) piezas.push({ n, a: m.index, b: m.index + m[0].length, w: m[1], coma: !!m[2], punto: !!m[3] });
      }
      let t = audio.currentTime + 0.05, ms = 0;
      const marcas = [];
      piezas.forEach(x => {
        if (x.coma) { t += 0.16; ms += 160; return; }
        if (x.punto) { t += 0.42; ms += 420; return; }
        const b = banda(x.w), dur = Math.min(0.5, 0.07 + 0.017 * x.w.length);
        nota(t, frecuencia(b), dur, 0.09 + b * 0.006);
        if (terminos.has(x.w.toLowerCase())) { nota(t, frecuencia(b) * 1.5, dur * 2, 0.05, 'triangle'); nota(t, frecuencia(b) / 2, dur * 2, 0.05, 'triangle'); }
        marcas.push([ms, x]);
        t += dur * 0.9; ms += dur * 900;
      });
      marcas.forEach(([cuando, x]) => setTimeout(() => {
        if (estado.fin || !(window.CSS && CSS.highlights && window.Highlight)) return;
        try { const r = new Range(); r.setStart(x.n, x.a); r.setEnd(x.n, x.b); CSS.highlights.set('partitura', new Highlight(r)); } catch (e) {}
      }, cuando));
      i++;
      estado.reloj = setTimeout(tocarPar, ms + 600);
    };
    tocarPar();
  }

  /* ── huella (solo en este navegador) ── */
  const HUELLA = 'p314b_huella';
  function leerHuella() {
    try { const h = JSON.parse(localStorage.getItem(HUELLA) || 'null'); if (h && h.v === 1) return h; } catch (e) {}
    return { v: 1, pasos: [], tiempo: {}, titulos: {} };
  }
  function escribirHuella(h) {
    if (h.pasos.length > 3000) h.pasos = h.pasos.slice(-3000);
    try { localStorage.setItem(HUELLA, JSON.stringify(h)); } catch (e) {}
  }
  /* Huella colectiva (worker/huella.js): solo pares [de, a] de textos, sin
     hora ni quién. No se manda nada si la huella está pausada o si el
     navegador pide no ser rastreado (Do Not Track / Global Privacy Control). */
  const COLA = 'p314b_huella_envio';
  const noRastrear = () => navigator.globalPrivacyControl === true || navigator.doNotTrack === '1' || window.doNotTrack === '1';
  function encolarPar(de, a) {
    if (op.sinHuella || noRastrear()) return;
    try { const c = JSON.parse(sessionStorage.getItem(COLA) || '[]'); c.push([de, a]); sessionStorage.setItem(COLA, JSON.stringify(c.slice(-20))); } catch (e) {}
  }
  function mandarPares() {
    let c = [];
    try { c = JSON.parse(sessionStorage.getItem(COLA) || '[]'); } catch (e) {}
    if (!c.length || op.sinHuella || noRastrear() || !navigator.sendBeacon) return;
    try { if (navigator.sendBeacon('/api/huella', new Blob([JSON.stringify({ pares: c })], { type: 'application/json' }))) sessionStorage.removeItem(COLA); } catch (e) {}
  }
  addEventListener('pagehide', mandarPares);
  document.addEventListener('visibilitychange', () => { if (document.hidden) mandarPares(); });

  /* Cómo se lee cada texto (worker/huella.js → /api/lectura): por cada texto,
     cuántos segundos se estuvo y qué se hizo adentro (diagonal, hojear, nota,
     marca, pariente, mismizar, opción del panel, copiar, capítulo). El Worker
     le suma la hora (entera), la zona y el clima. No lleva ningún
     identificador: ni de persona, ni de sesión, ni de dispositivo. Mismas
     reglas que los pares: nada si la huella está pausada o el navegador pide
     no ser rastreado. */
  const COLA_LEC = 'p314b_lectura_envio';
  let vis = null, slugVisita = '';   // la visita en curso: { slug, desde, i }
  const abrirVisita = slug => { slugVisita = slug; vis = { slug, desde: Date.now(), i: {} }; };
  const anotar = tipo => { if (vis) vis.i[tipo] = (vis.i[tipo] || 0) + 1; };
  const tipoDeClick = el => {
    const m = el.closest && el.closest('.accion-mark[data-visual], .hf, .par-card, [data-ex], .ex-op, .btn-mismizar, [data-mismizar]');
    if (!m) return null;
    if (m.matches('.accion-mark')) {
      const v = m.dataset.visual;
      return v === 'diagonal' ? 'diagonal' : v === 'hojear' ? 'hojear' : (v === 'nota' || v === 'marginalia') ? 'nota' : v === 'ancla' ? null : 'marca';
    }
    if (m.matches('.hf, .par-card')) return 'pariente';
    if (m.matches('.btn-mismizar, [data-mismizar]')) return 'mismizar';
    return 'opcion';
  };
  document.addEventListener('click', e => { const t = tipoDeClick(e.target); if (t) anotar(t); }, true);
  document.addEventListener('copy', () => anotar('copiar'));
  function cerrarVisita() {
    if (!vis) return;
    const v = vis; vis = null;
    if (op.sinHuella || noRastrear()) return;
    const seg = Math.min(3600, Math.round((Date.now() - v.desde) / 1000));
    if (seg < 3 && !Object.keys(v.i).length) return;
    try { const c = JSON.parse(sessionStorage.getItem(COLA_LEC) || '[]'); c.push({ t: v.slug, s: seg, i: v.i }); sessionStorage.setItem(COLA_LEC, JSON.stringify(c.slice(-20))); } catch (e) {}
  }
  function mandarLecturas() {
    cerrarVisita();
    let c = [];
    try { c = JSON.parse(sessionStorage.getItem(COLA_LEC) || '[]'); } catch (e) {}
    if (!c.length || op.sinHuella || noRastrear() || !navigator.sendBeacon) return;
    try { if (navigator.sendBeacon('/api/lectura', new Blob([JSON.stringify({ lecturas: c })], { type: 'application/json' }))) sessionStorage.removeItem(COLA_LEC); } catch (e) {}
  }
  addEventListener('pagehide', mandarLecturas);
  // al esconder la pestaña se cierra y se manda la visita; al volver empieza
  // otra del mismo texto: lo que pasó con la pestaña oculta no cuenta
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) mandarLecturas();
    else if (slugVisita && !op.sinHuella) abrirVisita(slugVisita);
  });

  let actual = null, desde = 0;
  function sumarTiempo() {
    if (!actual || !desde || document.hidden) { desde = document.hidden ? 0 : Date.now(); return; }
    const seg = Math.min(600, Math.round((Date.now() - desde) / 1000));
    desde = Date.now();
    if (seg < 1 || op.sinHuella) return;
    const h = leerHuella();
    const t = h.tiempo[actual.slug] = h.tiempo[actual.slug] || {};
    t[actual.idx] = (t[actual.idx] || 0) + seg;
    escribirHuella(h);
  }
  setInterval(sumarTiempo, 15000);
  document.addEventListener('visibilitychange', sumarTiempo);
  addEventListener('pagehide', sumarTiempo);
  function paso(slug, idx, titulo, total) {
    if (document.documentElement.classList.contains('en-panel')) return; // lo abierto al costado no cuenta
    parar();
    sumarTiempo();
    if (!vis || vis.slug !== slug) { cerrarVisita(); abrirVisita(slug); } else anotar('capitulo');
    actual = { slug, idx }; desde = Date.now();
    if (op.sinHuella) return;
    const h = leerHuella();
    const ult = h.pasos[h.pasos.length - 1];
    // huella colectiva: el paso de un texto a otro (dentro de 3 horas) se
    // anota para mandarlo, sin nada más, al irse de la página
    if (ult && ult[1] !== slug && Date.now() / 1000 - ult[0] < 3 * 3600) encolarPar(ult[1], slug);
    if (!ult || ult[1] !== slug || ult[2] !== idx) h.pasos.push([Math.round(Date.now() / 1000), slug, idx]);
    if (titulo) h.titulos[slug] = titulo;
    if (total) (h.partes = h.partes || {})[slug] = total;
    escribirHuella(h);
  }

  /* ── parientes: familia y genealogía de una palabra ── */
  let par = null, parFormas = null, card = null;
  async function cargarParientes() {
    if (par) return par;
    par = await datos('parientes.json') || { o: [], f: [], u: {} };
    parFormas = new Map();
    Object.entries(par.u || {}).forEach(([forma, [fi]]) => { if (!parFormas.has(fi)) parFormas.set(fi, []); parFormas.get(fi).push(forma); });
    return par;
  }
  const escH = P314.esc;
  function palabraEn(x, y) {
    let nodo, off;
    if (document.caretPositionFromPoint) { const c = document.caretPositionFromPoint(x, y); if (!c) return null; nodo = c.offsetNode; off = c.offset; }
    else if (document.caretRangeFromPoint) { const r = document.caretRangeFromPoint(x, y); if (!r) return null; nodo = r.startContainer; off = r.startOffset; }
    if (!nodo || nodo.nodeType !== 3) return null;
    const v = nodo.nodeValue, letra = /[\p{L}\-]/u;
    let a = off, b = off;
    while (a > 0 && letra.test(v[a - 1])) a--;
    while (b < v.length && letra.test(v[b])) b++;
    const w = v.slice(a, b).replace(/^-+|-+$/g, '');
    return w || null;
  }
  function cerrarCard() { if (card) { card.remove(); card = null; } }
  function mostrarFamilia(w, x, y) {
    const k = w.toLowerCase(), hit = par.u[k];
    cerrarCard();
    card = document.createElement('div');
    card.className = 'par-card';
    card.setAttribute('role', 'dialog');
    if (!hit) {
      card.innerHTML = `<button class="par-x" aria-label="cerrar">×</button><h4>${escH(w)}</h4><div class="par-nota">Sin familia en el corpus en línea: es una palabra sola, o sus parientes todavía no están publicados.</div>`;
    } else {
      const [fi, yo] = hit, f = par.f[fi];
      const grupos = f.s.map(g => `<div class="par-grupo">${g.map(m => `<span class="${m === yo ? 'yo' : ''}">${escH(m)}</span>`).join('')}</div>`)
        .join('<div class="par-sep">· el uso las separa ·</div>');
      // genealogía: una fila por miembro, una columna por año
      const miembros = f.s.flat();
      const obras = par.o, anios = obras.map(o => +(String(o[2] || '').slice(0, 4)) || null);
      const usados = miembros.flatMap(m => (f.m[m] ? f.m[m].g : []).map(([oi]) => anios[oi]).filter(Boolean));
      const a0 = Math.min(...usados, 9999), a1 = Math.max(...usados, 0);
      const W = 380, izq = 92, fila = 18, H = 22 + miembros.length * fila;
      const X = a => a1 > a0 ? izq + (a - a0) / (a1 - a0) * (W - izq - 12) : izq + (W - izq) / 2;
      let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="genealogía de la familia">`;
      for (let a = a0; a <= a1 && a1 - a0 < 40; a++) svg += `<text x="${X(a)}" y="10" text-anchor="middle">${a1 - a0 > 6 && a % 2 ? '' : "'" + String(a).slice(2)}</text>`;
      miembros.forEach((m, i) => {
        const yy = 22 + i * fila;
        svg += `<text x="0" y="${yy + 3}">${escH(m.length > 15 ? m.slice(0, 14) + '…' : m)}</text>`;
        const vistos = {};
        (f.m[m] ? f.m[m].g : []).forEach(([oi, n]) => {
          const a = anios[oi]; if (!a) return;
          const dx = (vistos[a] = (vistos[a] || 0) + 1) - 1;
          svg += `<circle class="pg${m === yo ? ' yo' : ''}" data-o="${escH(obras[oi][0])}" cx="${(X(a) + dx * 3).toFixed(1)}" cy="${yy}" r="${Math.min(7, 1.6 + Math.sqrt(n) * 0.9).toFixed(1)}"><title>${escH(obras[oi][1])} (${escH(obras[oi][2])}): ${n}</title></circle>`;
        });
      });
      svg += '</svg>';
      const p = f.m[yo] && f.m[yo].p;
      card.innerHTML = `<button class="par-x" aria-label="cerrar">×</button><h4>${escH(yo)}</h4>`
        + `<div class="par-sub">familia «${escH(f.r)}-» · ${miembros.length} miembros${p ? ' · aparece por primera vez en ' + escH(p) : ''}</div>`
        + grupos + svg
        + '<div class="par-nota">Cada punto, un texto en línea donde aparece (más grande, más veces), por año de escritura. Tocalo para ir.</div>';
      card.querySelectorAll('.pg').forEach(c => c.addEventListener('click', () => { location.href = BASE + 'obras/' + c.dataset.o + '.html'; }));
    }
    document.body.appendChild(card);
    const r = card.getBoundingClientRect();
    card.style.left = Math.max(12, Math.min(innerWidth - r.width - 12, x - r.width / 2)) + 'px';
    card.style.top = (y + 18 + r.height < innerHeight ? y + 18 : Math.max(12, y - r.height - 18)) + 'px';
    card.querySelector('.par-x').addEventListener('click', cerrarCard);
    card.addEventListener('click', e => e.stopPropagation());
  }
  document.addEventListener('click', e => {
    if (!op.parientes || !contActual || !contActual.contains(e.target)) { if (card && !(card.contains(e.target))) cerrarCard(); return; }
    if (e.target.closest('a, button, .accion-mark, .katex, .mz-btn, .homo') || (getSelection() + '').trim()) return;
    const w = palabraEn(e.clientX, e.clientY);
    if (!w) { cerrarCard(); return; }
    cargarParientes().then(() => mostrarFamilia(w, e.clientX, e.clientY));
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrarCard(); });

  /* ── mismizar: el párrafo se recompone con los parientes de sus palabras ── */
  let mzBtn = null, mzPar = null;
  const mzActivos = new Map(); // párrafo → { html, reloj }
  function mismizar(p) {
    if (mzActivos.has(p)) {
      const m = mzActivos.get(p); clearInterval(m.reloj); p.innerHTML = m.html; p.classList.remove('mz-fijo'); mzActivos.delete(p);
      if (mzBtn) mzBtn.classList.remove('activo');
      return;
    }
    const html = p.innerHTML;
    const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentNode.closest('.katex') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    const nodos = []; let n; while ((n = w.nextNode())) nodos.push(n);
    const piezas = [];
    nodos.forEach(n => {
      const frag = document.createDocumentFragment(); let pos = 0, m;
      const rx = /[\p{L}][\p{L}\-]*/gu;
      // lo que queda entre palabras (puntuación, espacios) también se borra,
      // pero deja un espacio para que las palabras no se peguen
      const entre = t => {
        const s = document.createElement('span'); s.className = 'mz'; s.textContent = t;
        piezas.push({ s, sep: true }); frag.appendChild(s);
      };
      while ((m = rx.exec(n.nodeValue))) {
        if (m.index > pos) entre(n.nodeValue.slice(pos, m.index));
        const s = document.createElement('span'); s.className = 'mz'; s.textContent = m[0];
        const hit = par.u[m[0].toLowerCase()];
        piezas.push({ s, fam: hit ? hit[0] : null, orig: m[0] });
        frag.appendChild(s); pos = m.index + m[0].length;
      }
      if (pos < n.nodeValue.length) entre(n.nodeValue.slice(pos));
      n.replaceWith(frag);
    });
    // Sin azar: cada palabra recorre las formas de su familia en orden y, en
    // la última ronda, queda en la forma «misma» de la familia (la más usada
    // en el corpus). Lo que no tiene familia se borra. El párrafo termina
    // siempre en la misma figura: las familias que vuelven se repiten
    // idénticas, como un loop, y ahí se queda quieto.
    let ronda = 0;
    const paso = () => {
      ronda++;
      const fin = ronda >= MZ_RONDAS;
      piezas.forEach((x, i) => {
        if (x.sep) {
          if (/^\s+$/.test(x.s.textContent)) return;
          if (fin) { x.s.textContent = ' '; x.s.style.opacity = ''; }
          else x.s.style.opacity = Math.max(0, 1 - ronda / (MZ_RONDAS - 1));
        } else if (x.fam != null) {
          const otras = parFormas.get(x.fam) || [];
          const nueva = fin || otras.length < 2 ? misma(x.fam) : otras[(i + ronda) % otras.length];
          if (nueva) x.s.textContent = conMayuscula(x.orig, nueva);
        } else {
          const o = Math.max(0, 1 - ronda / (MZ_RONDAS - 1));
          x.s.style.opacity = o;
          if (!o) x.s.style.display = 'none';
        }
      });
      if (fin) {
        const m = mzActivos.get(p);
        if (m) { clearInterval(m.reloj); m.reloj = 0; }
        p.classList.add('mz-fijo');
      }
    };
    mzActivos.set(p, { html, reloj: 0 });
    if (quieto) { while (ronda < MZ_RONDAS) paso(); }
    else { paso(); mzActivos.get(p).reloj = setInterval(paso, 900); }
    if (mzBtn) mzBtn.classList.add('activo');
  }
  const MZ_RONDAS = 6;
  const mismas = new Map();
  // la forma «misma» de una familia: el miembro que más aparece en el corpus
  function misma(fi) {
    if (mismas.has(fi)) return mismas.get(fi);
    const f = par.f[fi];
    let mejor = f ? f.r : null, max = -1;
    if (f) Object.entries(f.m || {}).forEach(([w, d]) => {
      const n = (d.g || []).reduce((s, g) => s + g[1], 0);
      if (n > max) { max = n; mejor = w; }
    });
    mismas.set(fi, mejor);
    return mejor;
  }
  function ubicarMz(p) {
    if (!mzBtn) {
      mzBtn = document.createElement('button');
      mzBtn.className = 'mz-btn'; mzBtn.type = 'button'; mzBtn.textContent = '∞';
      mzBtn.title = 'mismizar este párrafo (otra vez: devolverlo)';
      mzBtn.addEventListener('click', e => { e.stopPropagation(); if (mzPar) cargarParientes().then(() => mismizar(mzPar)); });
      document.body.appendChild(mzBtn);
    }
    mzPar = p;
    const r = p.getBoundingClientRect();
    mzBtn.style.left = (r.left + scrollX - 34) + 'px';
    mzBtn.style.top = (r.top + scrollY + 2) + 'px';
    mzBtn.style.display = 'block';
    mzBtn.classList.toggle('activo', mzActivos.has(p));
  }
  document.addEventListener('mouseover', e => {
    if (!op.mismizar || !contActual) return;
    if (mzBtn && e.target === mzBtn) return;
    const p = e.target.closest && e.target.closest('#text-body p, #text-body li, #text-body blockquote');
    if (p && contActual.contains(p)) ubicarMz(p);
  });
  function apagarMz() {
    mzActivos.forEach((m, p) => { clearInterval(m.reloj); if (p.isConnected) { p.innerHTML = m.html; p.classList.remove('mz-fijo'); } });
    mzActivos.clear();
    if (mzBtn) mzBtn.style.display = 'none';
  }

  /* ── panel ── */
  let elPanel = null, rehacer = null, contActual = null;
  const OPS = [['oir', 'oír mal a propósito', 'Toda palabra de la lista de homófonos se lee como su par'],
               ['sismo', 'sismógrafo', 'Una franja al costado: dónde se espesa el texto'],
               ['parientes', 'parientes', 'Tocar una palabra muestra su familia y en qué textos aparece cada pariente, por año'],
               ['mismizar', 'mismizar ∞', 'Un botón ∞ junto a cada párrafo lo recompone con los parientes de sus palabras']];
  function pintarBotones() {
    if (!elPanel) return;
    elPanel.innerHTML = '<div class="ex-tit">otras lecturas</div><div class="ex-ops">'
      + OPS.map(([k, t, d]) => `<button class="ex-op" data-ex="${k}" title="${d}" aria-pressed="${!!op[k]}">${t}</button>`).join('')
      + `<button class="ex-op" data-ex="partitura" title="Escuchar el texto desde el párrafo en pantalla: más agudo, más raro" aria-pressed="${!!sonando}">${sonando ? '■ parar partitura' : '▶ partitura'}</button>`
      + `<a class="ex-op" href="${BASE}huella.html" title="Lo que leíste, en qué orden y cuánto (solo en este navegador)">mi huella ↗</a>`
      + '</div>';
    elPanel.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      const k = b.dataset.ex;
      if (k === 'partitura') { if (contActual) tocar(contActual); return; }
      op[k] = !op[k]; guardar(); pintarBotones();
      if (k === 'oir') { if (op.oir) pintar(contActual); else if (rehacer) rehacer(); }
      if (k === 'sismo') sismografo(contActual);
      if (k === 'parientes') { document.body.classList.toggle('ex-parientes', !!op.parientes); if (op.parientes) cargarParientes(); else cerrarCard(); }
      if (k === 'mismizar') { if (op.mismizar) cargarParientes(); else apagarMz(); }
    }));
  }
  function panel(el, alRehacer) { elPanel = el; rehacer = alRehacer; pintarBotones(); }
  // Lo usan las intenciones del panel de lectura: deja prendidas solo las
  // otras lecturas que vienen en «cuales» ({ oir: true, … }); la huella no
  // se toca.
  function fijar(cuales) {
    const antes = Object.assign({}, op);
    OPS.forEach(([k]) => { if (cuales && cuales[k]) op[k] = true; else delete op[k]; });
    guardar(); pintarBotones();
    if (!!antes.oir !== !!op.oir) { if (op.oir) pintar(contActual); else if (rehacer) rehacer(); }
    if (!!antes.sismo !== !!op.sismo) sismografo(contActual);
    document.body.classList.toggle('ex-parientes', !!op.parientes);
    if (op.parientes || op.mismizar) cargarParientes();
    if (!op.parientes) cerrarCard();
    if (!op.mismizar) apagarMz();
  }
  const estado = () => { const e = {}; OPS.forEach(([k]) => { if (op[k]) e[k] = true; }); return e; };

  function pintar(cont) {
    if (!cont) return;
    if (contActual !== cont || !cont.isConnected) parar();
    mzActivos.forEach(m => clearInterval(m.reloj)); mzActivos.clear();
    if (mzBtn) mzBtn.style.display = 'none';
    cerrarCard();
    document.body.classList.toggle('ex-parientes', !!op.parientes);
    contActual = cont;
    if (op.oir) {
      if (hfMapa) forzar(cont);
      else cargarHomofonos().then(() => forzar(cont));
    }
    sismografo(cont);
  }

  if (op.oir) cargarHomofonos();
  if (op.sismo) cargarRareza();
  if (op.parientes || op.mismizar) cargarParientes();
  window.EXTRA = { pintar, panel, paso, parar, fijar, estado };
})();
