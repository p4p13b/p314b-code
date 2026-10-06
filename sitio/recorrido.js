/* recorrido.js — compartido por obra-template.html y pdf-post-template.html.
   Usa las globales SLUG, ACCIONES e irAAccion(id) de la página.
   Va al final del body, después del script principal. */
/* Tu rastro: qué textos leíste y qué diagonales seguiste, para que el
   mapa los marque. Solo en este navegador (localStorage); no sale de acá. */
(function(){
  var KEY = 'p314b_rastro';
  function leer(){ try { var r = JSON.parse(localStorage.getItem(KEY) || '{}'); return { obras: r.obras || {}, diagonales: r.diagonales || {} }; } catch (e) { return { obras: {}, diagonales: {} }; } }
  window.p314bRastro = function (tipo, id) {
    if (!id || document.documentElement.classList.contains('en-panel')) return;
    var r = leer(); r[tipo][id] = Date.now();
    try { localStorage.setItem(KEY, JSON.stringify(r)); } catch (e) {}
  };
  p314bRastro('obras', SLUG);

  // El trayecto de esta visita (sessionStorage: se borra al cerrar la
  // pestaña): por qué textos pasó, en orden, y la última diagonal que
  // siguió. Lo usa el filtro de diagonales (abajo) y el mapa.
  var enPanel = document.documentElement.classList.contains('en-panel');
  var ARCHIVO = decodeURIComponent(location.pathname.split('/').pop() || '');
  if (!enPanel) {
    try {
      var tr = JSON.parse(sessionStorage.getItem('p314b_trayecto') || '[]');
      if (!tr.length || tr[tr.length - 1].obra !== SLUG) tr.push({ obra: SLUG, archivo: ARCHIVO, t: Date.now() });
      if (tr.length > 60) tr = tr.slice(0, 1).concat(tr.slice(-59));
      sessionStorage.setItem('p314b_trayecto', JSON.stringify(tr));
    } catch (e) {}
  }
  window.p314bLlegada = function (origenId, destinoId) {
    if (enPanel) return;
    var t = ((ACCIONES[origenId] || {}).tipos || []).find(function (x) { return x.tipo === 'diagonal' && (!destinoId || x.destino === destinoId); });
    if (!t) return;
    try {
      sessionStorage.setItem('p314b_llegada', JSON.stringify({ desde: SLUG, archivo: ARCHIVO, accion: origenId, destino: t.destino,
        instrumento: t.instrumento || null, relacion: t.tipo_relacion || null, t: Date.now() }));
      if (t.instrumento) {
        var ins = JSON.parse(sessionStorage.getItem('p314b_instrumentos') || '[]');
        if (ins.indexOf(t.instrumento) < 0) { ins.push(t.instrumento); sessionStorage.setItem('p314b_instrumentos', JSON.stringify(ins.slice(-30))); }
      }
    } catch (e) {}
  };

  // Seguir una diagonal (tarjeta, lectura, recorrido): se anota su origen.
  var ir = irAAccion;
  window.irAAccionSinRastro = ir;
  irAAccion = function (destinoId) {
    Object.keys(ACCIONES).forEach(function (id) {
      (ACCIONES[id].tipos || []).forEach(function (t) { if (t.tipo === 'diagonal' && t.destino === destinoId) { p314bRastro('diagonales', id); p314bLlegada(id, destinoId); } });
    });
    return ir.apply(this, arguments);
  };
})();

/* Recorridos de lectura: un camino entre anclas de varias obras, con
   anterior / siguiente. Se entra desde el mapa con
   #accion=ID&recorrido=RID&paso=N; la barra de abajo lleva de parada en
   parada. Los recorridos los calcula matriz/calcular_recorridos.py y
   publicar.py los recorta a lo que está en línea (recorridos.json). */
(function(){
  var mR = /[#&]recorrido=([^&]+)/.exec(location.hash);
  if (!mR || document.documentElement.classList.contains('en-panel')) return;
  var rid = decodeURIComponent(mR[1]);
  var mP = /[#&]paso=(\d+)/.exec(location.hash);
  var paso = mP ? +mP[1] : 0;
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  // En tu máquina (sitio/ servido en local) no hay recorridos.json: se
  // arman las paradas desde matriz/recorridos.json, sin recortar.
  function paradasDe(r) {
    var out = [];
    (r.pasos || []).forEach(function (p) {
      [[p.desde || {}, null], [p.hacia || {}, p.diagonal]].forEach(function (x) {
        var e = x[0];
        if (!e.accion || (out.length && out[out.length - 1].accion === e.accion)) return;
        out.push({ accion: e.accion, obra: e.sitio, titulo: e.titulo || e.sitio, archivo: e.sitio + '.html', diagonal: x[1] });
      });
    });
    return { id: r.id, etiqueta: r.etiqueta || r.id, criterio: r.criterio, paradas: out };
  }
  fetch('../recorridos.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(function (d) { return d.recorridos || []; })
    .catch(function () { return fetch('../matriz/recorridos.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (d) { return (d.recorridos || []).map(paradasDe); }); })
    .then(function (lista) { var rec = lista.find(function (r) { return r.id === rid; }); if (rec && rec.paradas.length > 1) montar(rec); })
    .catch(function () {});

  // Estilos de la barra (los comparten obras y posteos-PDF).
  var estilo = document.createElement('style');
  estilo.textContent = [
    '.rec-barra{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:65;display:flex;align-items:center;gap:14px;max-width:calc(100vw - 32px);background:color-mix(in oklab,var(--bg) 94%,transparent);backdrop-filter:blur(10px);border:1px solid var(--rule);border-left:2px solid var(--mark);border-radius:4px;padding:8px 10px 8px 14px;font-family:var(--font-mono);font-size:12px;color:var(--ink-soft);box-shadow:0 12px 32px rgba(0,0,0,.35);}',
    '.rec-barra .rec-nom{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:26ch;}',
    '.rec-barra .rec-nom b{font-family:var(--font-body);font-style:italic;font-weight:400;font-size:15px;color:var(--ink);}',
    '.rec-puntos{display:flex;gap:5px;align-items:center;}',
    '.rec-puntos button{width:9px;height:9px;padding:0;border-radius:50%;border:1px solid var(--mark-lt);background:transparent;cursor:pointer;}',
    '.rec-puntos button.hecho{background:color-mix(in oklab,var(--mark) 45%,transparent);}',
    '.rec-puntos button.aca{background:var(--mark-lt);transform:scale(1.25);}',
    '.rec-puntos i{width:8px;border-top:1px dashed var(--ink-muted);}',
    '.rec-barra .rec-n{color:var(--ink-muted);white-space:nowrap;}',
    '.rec-barra button.rec-ir{font-family:var(--font-mono);font-size:12px;color:var(--ink);border:1px solid var(--line-ctl,var(--rule));border-radius:3px;padding:6px 10px;background:transparent;cursor:pointer;white-space:nowrap;}',
    '.rec-barra button.rec-ir:hover:not(:disabled){border-color:var(--ink);}',
    '.rec-barra button.rec-ir:disabled{opacity:.35;cursor:default;}',
    '.rec-barra button.rec-salir{color:var(--ink-muted);background:transparent;border:0;font-size:16px;cursor:pointer;padding:2px 6px;}',
    '.rec-barra button:focus-visible{outline:2px solid var(--mark-lt);outline-offset:2px;}',
    '@media (max-width:700px){.rec-barra{gap:8px;bottom:10px;}.rec-barra .rec-nom,.rec-puntos{display:none;}}'
  ].join('\n');
  document.head.appendChild(estilo);

  function montar(rec) {
    var P = rec.paradas;
    paso = Math.max(0, Math.min(P.length - 1, paso));
    var barra = document.createElement('nav');
    barra.className = 'rec-barra'; barra.setAttribute('aria-label', 'recorrido');
    document.body.appendChild(barra);

    function hash(n) { return '#accion=' + encodeURIComponent(P[n].accion) + '&recorrido=' + encodeURIComponent(rec.id) + '&paso=' + n; }
    function rotulo(n) { return P[n].obra === SLUG ? 'en este texto' : P[n].titulo; }
    function pintar() {
      var puntos = P.map(function (p, i) {
        var salto = i > 0 && !p.diagonal ? '<i title="salto: el recorrido sigue en otro lugar"></i>' : '';
        return salto + '<button type="button" data-ir="' + i + '" class="' + (i === paso ? 'aca' : i < paso ? 'hecho' : '') + '" title="' + esc((i + 1) + '. ' + p.titulo) + '" aria-label="parada ' + (i + 1) + ': ' + esc(p.titulo) + '"' + (i === paso ? ' aria-current="step"' : '') + '></button>';
      }).join('');
      var sig = paso < P.length - 1 ? P[paso + 1] : null;
      barra.innerHTML = '<span class="rec-nom">⤳ recorrido · <b>' + esc(rec.etiqueta) + '</b></span>'
        + '<span class="rec-puntos">' + puntos + '</span>'
        + '<span class="rec-n">' + (paso + 1) + ' / ' + P.length + '</span>'
        + '<button type="button" class="rec-ir" data-ir="' + (paso - 1) + '"' + (paso ? '' : ' disabled') + '>← anterior</button>'
        + '<button type="button" class="rec-ir" data-ir="' + (paso + 1) + '"' + (sig ? ' title="' + esc((sig.diagonal ? 'siguiendo la diagonal hacia ' : 'salto a ') + rotulo(paso + 1)) + '"' : ' disabled') + '>' + (sig ? 'siguiente →' : 'fin del recorrido') + '</button>'
        + '<button type="button" class="rec-salir" data-salir title="salir del recorrido" aria-label="salir del recorrido">×</button>';
    }
    function ir(n) {
      if (n < 0 || n >= P.length || n === paso) return;
      var p = P[n];
      if (n === paso + 1 && p.diagonal) { p314bRastro('diagonales', p.diagonal); p314bLlegada(p.diagonal, p.accion); }
      if (p.obra === SLUG) {
        history.replaceState(null, '', hash(n));
        paso = n; pintar();
        irAAccionSinRastro(p.accion);
      } else {
        location.href = encodeURIComponent(p.archivo) + hash(n);
      }
    }
    barra.addEventListener('click', function (e) {
      e.stopPropagation();
      var b = e.target.closest('button'); if (!b) return;
      if (b.hasAttribute('data-salir')) { history.replaceState(null, '', location.pathname + '#accion=' + encodeURIComponent(P[paso].accion)); barra.remove(); return; }
      if (b.dataset.ir != null) ir(+b.dataset.ir);
    });
    pintar();
  }
})();

/* Filtro de diagonales por trayectoria. Cuando un capítulo tiene más
   anclas de diagonal vacías (aceptadas desde la matriz, sin emergente)
   de las que el texto aguanta, se encienden solo las que tienen que ver
   con el camino de esta visita: el texto anterior, el inicial, la
   diagonal por la que se llegó (mismo instrumento o tipo de relación) y
   los textos ya pasados. Las demás quedan dormidas: el fragmento se lee
   como texto llano. Las diagonales con emergente de la autora se ven
   siempre, y también la diagonal a la que se llegó (#accion=…).
   Tope: max(DG_MIN, palabras del capítulo / DG_PALABRAS) vacías
   encendidas. El botón «diagonales» al lado de «marcas» lo apaga
   (localStorage, solo en este navegador). */
(function(){
  var DG_MIN = 3, DG_PALABRAS = 600, KEY = 'p314b_diag_filtro';
  var cuerpo = document.getElementById('text-body');
  if (!cuerpo || document.documentElement.classList.contains('en-panel')) return;
  var ARCHIVO = decodeURIComponent(location.pathname.split('/').pop() || '');
  function leerSesion(k, def) { try { return JSON.parse(sessionStorage.getItem(k) || 'null') || def; } catch (e) { return def; } }
  var tray = leerSesion('p314b_trayecto', []);
  var llegada = leerSesion('p314b_llegada', null);
  // Si la llegada no fue a este texto (se abrió otro desde el índice), no cuenta.
  if (llegada && !(ACCIONES[llegada.destino])) llegada = null;
  var previas = tray.filter(function (p) { return p.archivo !== ARCHIVO; });
  var inicial = tray.length && tray[0].archivo !== ARCHIVO ? tray[0].archivo : null;
  var anterior = previas.length ? previas[previas.length - 1].archivo : null;
  var visitadas = new Set(previas.map(function (p) { return p.archivo; }));
  // Instrumentos de las diagonales seguidas en esta visita.
  var seguidos = new Set(leerSesion('p314b_instrumentos', []));
  var objetivo = (/[#&]accion=([^&]+)/.exec(location.hash) || [])[1];
  objetivo = objetivo ? decodeURIComponent(objetivo) : null;

  function destinoArchivo(t) { var r = t._resuelto || {}; return r.mismaObra ? ARCHIVO : (r.archivo || null); }
  function diagonalesDe(id) { return ((ACCIONES[id] || {}).tipos || []).filter(function (t) { return t.tipo === 'diagonal'; }); }
  // Una acción es «vacía» si todas sus diagonales lo son.
  function esVacia(id) { var ds = diagonalesDe(id); return ds.length > 0 && ds.every(function (t) { return t.vacia; }); }
  function puntaje(id) {
    var mejor = 0;
    diagonalesDe(id).forEach(function (t) {
      var d = destinoArchivo(t), s = 0;
      if (d && d === anterior) s += 3;
      if (d && d === inicial) s += 2;
      if (d && visitadas.has(d)) s += 1;
      if (llegada && t.instrumento && t.instrumento === llegada.instrumento) s += 2;
      else if (t.instrumento && seguidos.has(t.instrumento)) s += 1;
      if (llegada && t.tipo_relacion && t.tipo_relacion === llegada.relacion) s += 1;
      if (llegada && t.destino === llegada.accion) s += 3; // la vuelta por donde se vino
      mejor = Math.max(mejor, s);
    });
    return mejor;
  }

  var estilo = document.createElement('style');
  estilo.textContent = '.accion-mark.dg-dormida{text-decoration:none!important;background:none!important;cursor:text!important;pointer-events:none;}'
    + '.accion-mark.dg-dormida::after{content:none!important;}'
    + '.dg-filtro .n{color:var(--ink-muted);}';
  document.head.appendChild(estilo);

  var modo = 'trayecto';
  try { if (localStorage.getItem(KEY) === 'todas') modo = 'todas'; } catch (e) {}
  var boton = null, cuenta = { total: 0, dormidas: 0 };

  function ponerBoton() {
    if (boton) return;
    var marcas = document.getElementById('btn-marcas');
    if (!marcas) return;
    boton = document.createElement('button');
    boton.type = 'button'; boton.className = 'nav-btn dg-filtro'; boton.id = 'btn-dg-filtro';
    boton.addEventListener('click', function () {
      modo = modo === 'todas' ? 'trayecto' : 'todas';
      try { localStorage.setItem(KEY, modo); } catch (e) {}
      pedir();
    });
    marcas.parentNode.insertBefore(boton, marcas.nextSibling);
  }
  function pintarBoton() {
    if (!cuenta.dormidas && modo === 'trayecto') { if (boton) boton.hidden = true; return; }
    ponerBoton(); if (!boton) return;
    boton.hidden = false;
    var visibles = cuenta.total - (modo === 'todas' ? 0 : cuenta.dormidas);
    boton.innerHTML = '◇<span class="lbl"> diagonales: ' + (modo === 'todas' ? 'todas' : 'tu camino') + '</span> <span class="n">' + visibles + '/' + cuenta.total + '</span>';
    boton.setAttribute('aria-pressed', modo === 'todas' ? 'false' : 'true');
    boton.title = modo === 'todas'
      ? 'Se ven todas las diagonales. Tocá para dejar encendidas solo las que tienen que ver con lo que venís leyendo.'
      : 'Hay ' + cuenta.total + ' diagonales en este capítulo; se encienden las que tienen que ver con lo que venís leyendo (y siempre las que tienen emergente). Tocá para ver todas.';
  }

  function aplicar() {
    pend = false;
    var marcas = Array.prototype.slice.call(cuerpo.querySelectorAll('.accion-mark[data-accion]'));
    // Acciones con diagonal en pantalla, en orden de lectura.
    var orden = [], vistas = new Set();
    marcas.forEach(function (m) {
      (m.dataset.accion || '').split(',').forEach(function (id) {
        if (id && !vistas.has(id) && diagonalesDe(id).length) { vistas.add(id); orden.push(id); }
      });
    });
    var vacias = orden.filter(esVacia);
    var palabras = (cuerpo.textContent.match(/[\p{L}\p{N}]+/gu) || []).length;
    var tope = Math.max(DG_MIN, Math.ceil(palabras / DG_PALABRAS));
    var dormidas = new Set();
    if (modo !== 'todas' && vacias.length > tope) {
      var cands = vacias.map(function (id, i) { return { id: id, i: i, s: puntaje(id) }; });
      var elegidas = new Set();
      if (objetivo && vistas.has(objetivo)) elegidas.add(objetivo);
      // Primero lo que se asocia al camino, de a un destino por vez
      // para no encender cinco veces el mismo texto.
      var asociadas = cands.filter(function (c) { return c.s > 0; }).sort(function (a, b) { return b.s - a.s || a.i - b.i; });
      var usados = new Set();
      [true, false].forEach(function (unaPorDestino) {
        asociadas.forEach(function (c) {
          if (elegidas.size >= tope || elegidas.has(c.id)) return;
          var d = destinoArchivo(diagonalesDe(c.id)[0]) || c.id;
          if (unaPorDestino && usados.has(d)) return;
          usados.add(d); elegidas.add(c.id);
        });
      });
      // El resto del cupo, repartido a lo largo del capítulo.
      var resto = cands.filter(function (c) { return !elegidas.has(c.id); });
      var faltan = tope - elegidas.size;
      for (var k = 0; k < faltan && resto.length; k++) elegidas.add(resto[Math.floor((k + 0.5) * resto.length / faltan)].id);
      vacias.forEach(function (id) { if (!elegidas.has(id)) dormidas.add(id); });
    }
    marcas.forEach(function (m) {
      var ids = (m.dataset.accion || '').split(',').filter(Boolean);
      // Dormida solo si todo lo que lleva la marca es una diagonal dormida
      // (o un ancla): una nota o una marginalia en el mismo fragmento la
      // mantienen encendida.
      var dormir = ids.some(function (id) { return dormidas.has(id); }) && ids.every(function (id) {
        return dormidas.has(id) || ((ACCIONES[id] || {}).tipos || []).every(function (t) { return t.tipo === 'ancla' || t.tipo === 'ancla-diagonal'; });
      });
      if (m.classList.contains('dg-dormida') !== dormir) m.classList.toggle('dg-dormida', dormir);
    });
    cuenta = { total: orden.length, dormidas: dormidas.size };
    // El riel de marcas (obra-template) se redibuja con este atributo.
    var firma = modo + ':' + Array.from(dormidas).join(',');
    if (document.documentElement.dataset.dgFiltro !== firma) document.documentElement.dataset.dgFiltro = firma;
    pintarBoton();
  }
  var pend = false;
  function pedir() { if (!pend) { pend = true; requestAnimationFrame(aplicar); } }
  new MutationObserver(pedir).observe(cuerpo, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-accion', 'data-visual'] });
  pedir();
  window.p314bFiltroDiagonales = { aplicar: pedir, estado: function () { return { modo: modo, cuenta: cuenta, inicial: inicial, anterior: anterior, llegada: llegada }; } };
})();
