/* matriz-obras.js — vista «obras» de matriz.html (solo la autora).

   Un grafo de fuerzas entre obras, pensado para leerse de a poco:
   - foco: se elige una obra (buscador o clic) y se ven sus vecinas a uno
     o dos saltos; «ver todo» muestra el corpus entero;
   - pocas líneas: cada obra muestra solo sus N relaciones del Cowork más
     fuertes (N se elige, 2 de entrada); en reposo van en un solo tono y
     el color por dimensión se prende aparte; cada dimensión se apaga;
   - tus diagonales siempre arriba (azul, con flecha); el grosor y el
     tamaño de las obras crecen con la cantidad, pero con tope, para que
     las obras con muchas diagonales no tapen el resto;
   - las propuestas del motor no se dibujan: van en el panel de la obra;
   - las obras sueltas (sin ningún vínculo a la vista) no orbitan el
     grupo: van en una franja aparte, debajo del grafo, separadas entre
     las que entran al sitio y las que no. Para las que entran hay una
     búsqueda de relaciones (léxico compartido, ver «buscador» abajo);
     lo que se conecta así es una relación hallada por la matriz: se
     dibuja punteada, se guarda en este navegador y se quita cuando
     quieras. No es una diagonal ni una relación del Cowork;
   - zoom y arrastre (rueda / pellizco / fondo), nodos que se arrastran y
     quedan fijos (doble clic los suelta), clic para seleccionar, Mayús+clic
     para sumar a la selección (se ve solo lo que pasa entre ellas), y
     obras o grupos enteros que se apagan; «ampliar» le da al grafo todo
     el ancho de la pantalla.

   Usa las globales de matriz.html (OBRAS, DIAGONALES, ANCLAS, RELACIONES,
   PROPUESTAS, pasaFiltro, titulo, instrEtiqueta, escHtml, leerJSON, $) y
   d3 v7. */
(function () {
  'use strict';
  const MO = window.MO = {};
  const COLORES = {
    concepto: '#a78bfa', figura: '#f59e0b', reescritura: '#ef4444', tema: '#22c55e', 'técnica': '#06b6d4',
    estilo: '#ec4899', 'género': '#f97316', lateral: '#14b8a6', firma: '#94a3b8', recurrencia: '#64748b',
    'filiación': '#eab308', secuencia: '#84cc16',
  };
  const colorDim = d => COLORES[d] || '#8a8a8a';
  const NEUTRO = '#b8a77a';       // relaciones del Cowork en reposo (sin color por dimensión)
  const HALLADA = '#e8e8e8';      // relaciones halladas por la búsqueda
  const CLAVE = 'p314b_matriz_obras_v2', CLAVE_VIEJA = 'p314b_matriz_obras';
  let est = { foco: null, saltos: 1, k: 2, dims: {}, color: false, ancho: false,
              capas: { diag: true, cowork: true, halladas: true }, grupos: { pdf: true, texto: true, fuera: true },
              ocultas: [], halladas: [] };
  try {
    const guardado = localStorage.getItem(CLAVE);
    if (guardado) Object.assign(est, JSON.parse(guardado));
    else {
      // de la versión anterior se conserva lo que apagaste, no la densidad
      const v = JSON.parse(localStorage.getItem(CLAVE_VIEJA) || '{}');
      ['ocultas', 'grupos', 'dims', 'saltos'].forEach(k => { if (v[k] != null) est[k] = v[k]; });
    }
  } catch (e) {}
  est.capas = Object.assign({ diag: true, cowork: true, halladas: true }, est.capas);
  est.halladas = est.halladas || [];
  const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(est)); } catch (e) {} };
  let sel = new Set(), posiciones = {}, sim = null, zoom = null, capa = null, hoverId = null;

  // ── datos ──
  function dimDominante(r) {
    let mejor = null, v = -1;
    Object.entries(r.dimensiones || {}).forEach(([k, x]) => { if (x > v) { v = x; mejor = k; } });
    return mejor || 'otra';
  }
  const entraAlSitio = o => o.en_linea !== false;
  function obraVisibleBase(o) {
    if (est.ocultas.includes(o.id)) return false;
    if (o.tipo_nodo === 'pdf' ? !est.grupos.pdf : !est.grupos.texto) return false;
    if (!o.en_linea && !est.grupos.fuera) return false;
    return true;
  }
  function modelo() {
    const obras = (typeof OBRAS !== 'undefined' ? OBRAS : []).filter(o => !o.diagonal);
    const porId = Object.fromEntries(obras.map(o => [o.id, o]));
    // diagonales tuyas, agregadas por par de obras
    const diag = {};
    (DIAGONALES || []).filter(d => typeof pasaFiltro !== 'function' || pasaFiltro(d)).forEach(d => {
      const a = ANCLAS[d.origen].sitio, b = ANCLAS[d.destino].sitio;
      if (!porId[a] || !porId[b]) return;
      const k = a + '→' + b;
      (diag[k] = diag[k] || { a, b, lista: [] }).lista.push(d);
    });
    // relaciones del Cowork
    const rels = ((typeof RELACIONES !== 'undefined' && RELACIONES && RELACIONES.relaciones) || [])
      .filter(r => r.a !== r.b && porId[r.a] && porId[r.b]).map(r => Object.assign({ dim: dimDominante(r) }, r));
    const dims = [...new Set(rels.map(r => r.dim))].sort();
    dims.forEach(d => { if (!(d in est.dims)) est.dims[d] = true; });
    // propuestas del motor, por obra (van al panel)
    const props = {};
    ((typeof PROPUESTAS !== 'undefined' && PROPUESTAS && PROPUESTAS.propuestas) || []).forEach(p => {
      [p.origen.sitio, p.destino.sitio].forEach(s => (props[s] = props[s] || []).push(p));
    });
    return { obras, porId, diag: Object.values(diag), rels, dims, props };
  }

  // ── qué se ve ──
  function recorte(M) {
    const base = new Set(M.obras.filter(obraVisibleBase).map(o => o.id));
    // Cowork: por obra, sus relaciones ordenadas (solo dimensiones prendidas)
    const porObra = {};
    M.rels.forEach(r => {
      if (!est.capas.cowork || !est.dims[r.dim] || !base.has(r.a) || !base.has(r.b)) return;
      (porObra[r.a] = porObra[r.a] || []).push(r); (porObra[r.b] = porObra[r.b] || []).push(r);
    });
    Object.values(porObra).forEach(l => l.sort((x, y) => y.peso - x.peso));
    const diagDe = id => est.capas.diag ? M.diag.filter(e => (e.a === id || e.b === id) && base.has(e.a) && base.has(e.b)) : [];
    const halladas = est.capas.halladas ? est.halladas.filter(h => base.has(h.a) && base.has(h.b) && M.porId[h.a] && M.porId[h.b]) : [];
    const halladasDe = id => halladas.filter(h => h.a === id || h.b === id);
    const otra = (r, id) => r.a === id ? r.b : r.a;
    const elegidas = new Set();
    let ids;
    if (est.foco && base.has(est.foco)) {
      // foco: sus 3·N relaciones más fuertes, sus diagonales y lo hallado;
      // a 2 saltos, las N más fuertes de cada vecina. Solo entra lo que se dibuja.
      ids = new Set([est.foco]);
      let borde = [est.foco];
      for (let s = 0; s < est.saltos; s++) {
        const nuevo = [];
        const sumar = o => { if (!ids.has(o)) { ids.add(o); nuevo.push(o); } };
        borde.forEach(id => {
          (porObra[id] || []).slice(0, s === 0 ? est.k * 3 : est.k).forEach(r => { elegidas.add(r); sumar(otra(r, id)); });
          diagDe(id).forEach(e => [e.a, e.b].forEach(sumar));
          halladasDe(id).forEach(h => sumar(otra(h, id)));
        });
        borde = nuevo;
      }
      // y las relaciones entre las que ya están, si son de las N más fuertes
      ids.forEach(id => (porObra[id] || []).slice(0, est.k).forEach(r => { if (ids.has(r.a) && ids.has(r.b)) elegidas.add(r); }));
    } else {
      ids = new Set(base);
      Object.values(porObra).forEach(l => l.slice(0, est.k).forEach(r => elegidas.add(r)));
    }
    const rels = [...elegidas];
    const diag = est.capas.diag ? M.diag.filter(e => ids.has(e.a) && ids.has(e.b)) : [];
    const hall = halladas.filter(h => ids.has(h.a) && ids.has(h.b));
    // sueltas: sin ningún vínculo a la vista; no entran al dibujo de fuerzas
    const conVinculo = new Set();
    rels.forEach(r => { conVinculo.add(r.a); conVinculo.add(r.b); });
    diag.forEach(e => { if (e.a !== e.b) { conVinculo.add(e.a); conVinculo.add(e.b); } });
    hall.forEach(h => { conVinculo.add(h.a); conVinculo.add(h.b); });
    const sueltas = [...ids].filter(id => !conVinculo.has(id) && id !== est.foco);
    sueltas.forEach(id => ids.delete(id));
    return { ids, rels, diag, hall, sueltas };
  }

  // ── dibujo ──
  function controlesHtml(M) {
    const opts = M.obras.slice().sort((a, b) => String(a.titulo).localeCompare(String(b.titulo), 'es'))
      .map(o => `<option value="${escHtml(o.titulo)}"></option>`).join('');
    const nH = est.halladas.length;
    return `<div class="mo-barra">
      <input id="mo-buscar" list="mo-lista" placeholder="buscar una obra…" value="${escHtml(est.foco && M.porId[est.foco] ? M.porId[est.foco].titulo : '')}" autocomplete="off">
      <datalist id="mo-lista">${opts}</datalist>
      <label>vecinas <select id="mo-saltos"><option value="1">a 1 salto</option><option value="2">a 2 saltos</option></select></label>
      <button id="mo-todo" class="mo-b">ver todo</button>
      <label>vínculos por obra <input type="range" id="mo-k" min="1" max="8" value="${est.k}"> <b id="mo-k-n">${est.k}</b></label>
      <button id="mo-ancho" class="mo-b" aria-pressed="${est.ancho}">${est.ancho ? '⤡ reducir' : '⤢ ampliar'}</button>
    </div>
    <details class="mo-capas" id="mo-capas"${est._capasAbiertas ? ' open' : ''}>
      <summary>capas, dimensiones y grupos</summary>
      <div class="mo-barra">
        <label><input type="checkbox" id="mo-c-diag"${est.capas.diag ? ' checked' : ''}> <span style="color:var(--mark-lt)">━▸</span> tus diagonales</label>
        <label><input type="checkbox" id="mo-c-hall"${est.capas.halladas ? ' checked' : ''}> <span style="color:${HALLADA}">┄</span> halladas por la búsqueda${nH ? ' (' + nH + ')' : ''}</label>
        <label><input type="checkbox" id="mo-c-cowork"${est.capas.cowork ? ' checked' : ''}> <span style="color:${NEUTRO}">━</span> relaciones del Cowork</label>
        <label><input type="checkbox" id="mo-color"${est.color ? ' checked' : ''}> colorear por dimensión</label>
      </div>
      <div class="mo-barra">
        ${M.dims.map(d => `<label class="mo-dim"><input type="checkbox" data-dim="${escHtml(d)}"${est.dims[d] ? ' checked' : ''}><i style="background:${colorDim(d)}"></i>${escHtml(d)}</label>`).join('')}
      </div>
      <div class="mo-barra">
        <label><input type="checkbox" id="mo-g-texto"${est.grupos.texto ? ' checked' : ''}> escritas</label>
        <label><input type="checkbox" id="mo-g-pdf"${est.grupos.pdf ? ' checked' : ''}> PDF</label>
        <label><input type="checkbox" id="mo-g-fuera"${est.grupos.fuera ? ' checked' : ''}> no publicadas</label>
        <button id="mo-soltar" class="mo-b">soltar nodos</button>
        ${est.ocultas.length ? `<button id="mo-mostrar" class="mo-b">mostrar apagadas (${est.ocultas.length})</button>` : ''}
      </div>
      <div class="mo-ayuda">rueda o pellizco: zoom · arrastrar el fondo: mover · arrastrar una obra: fijarla (doble clic la suelta) · clic: elegir · Mayús+clic: sumar</div>
    </details>
    <svg id="mo-svg" role="img" aria-label="Grafo de obras"></svg>
    <div id="mo-sueltas" class="mo-sueltas"></div>`;
  }
  const CSS = `
.mo-barra{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:0 0 10px;font-family:var(--font-mono);font-size:10.5px;color:var(--ink-muted);letter-spacing:.04em;}
.mo-barra input[type=range]{width:90px;vertical-align:middle;}
.mo-barra select,.mo-barra #mo-buscar{background:var(--bg-alt);color:var(--ink);border:1px solid var(--rule);font:inherit;padding:4px 7px;border-radius:2px;}
.mo-barra #mo-buscar{min-width:220px;}
.mo-b{background:none;border:1px solid var(--rule);color:var(--ink-soft);font:inherit;padding:4px 9px;border-radius:2px;cursor:pointer;}
.mo-b:hover{color:var(--ink);border-color:var(--ink-soft);}
.mo-b[disabled]{opacity:.5;cursor:default;}
.mo-dim i{display:inline-block;width:10px;height:3px;border-radius:2px;margin:0 4px 2px 2px;vertical-align:middle;}
.mo-ayuda{color:var(--ink-ghost);font-family:var(--font-mono);font-size:9.5px;margin:-2px 0 6px;}
.mo-capas{margin:0 0 10px;}
.mo-capas>summary{cursor:pointer;font-family:var(--font-mono);font-size:10.5px;color:var(--ink-muted);letter-spacing:.04em;margin-bottom:8px;width:max-content;}
.mo-capas>summary:hover{color:var(--ink);}
#mo-svg{width:100%;height:clamp(620px,calc(100vh - 170px),1150px);background:var(--bg-alt);border:1px solid var(--rule);border-radius:3px;cursor:grab;touch-action:none;display:block;}
#mo-svg:active{cursor:grabbing;}
.mo-n circle{stroke:var(--bg);stroke-width:1.5px;cursor:pointer;}
.mo-n text{font-family:var(--font-mono);font-size:9.5px;fill:var(--ink-soft);pointer-events:none;paint-order:stroke;stroke:var(--bg-alt);stroke-width:3px;}
.mo-n.foco circle{stroke:var(--ink);stroke-width:2.5px;}
.mo-n.sel circle{stroke:var(--mark-lt);stroke-width:3px;}
.mo-n.fijo circle{stroke-dasharray:2 2;}
.mo-n.hallada circle{stroke:${HALLADA};stroke-width:1.5px;stroke-dasharray:3 2;}
.mo-e{fill:none;}
.mo-e.diag{stroke:var(--mark-lt);}
.mo-e.hall{stroke:${HALLADA};stroke-dasharray:5 4;}
.mo-dim-apag{opacity:.08;}
.mo-lista .det-row{cursor:pointer;} .mo-lista .det-row:hover{color:var(--ink);}
.mo-acc{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0;}
.mo-sueltas{font-family:var(--font-mono);font-size:10.5px;color:var(--ink-muted);margin-top:10px;line-height:1.7;}
.mo-sueltas .fila{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px;}
.mo-sueltas .cab{color:var(--ink-soft);margin-right:6px;}
.mo-chip{background:var(--bg-alt);border:1px solid var(--rule);color:var(--ink-soft);font:inherit;padding:2px 8px;border-radius:10px;cursor:pointer;}
.mo-chip:hover,.mo-chip.sel{color:var(--ink);border-color:var(--mark-lt);}
.mo-chip.fuera{opacity:.55;border-style:dashed;}
.mo-cand{border-top:1px solid var(--rule);padding:7px 0;}
.mo-cand .t{color:var(--ink);cursor:pointer;}
.mo-cand .t:hover{text-decoration:underline;}
.mo-cand .fam{color:var(--ink-ghost);font-size:10px;}
.mo-cand .mo-b{float:right;margin-left:8px;padding:2px 7px;}
.mo-busca{display:flex;gap:6px;margin:8px 0 4px;}
.mo-busca input{flex:1;min-width:0;background:var(--bg-alt);color:var(--ink);border:1px solid var(--rule);font:inherit;padding:4px 7px;border-radius:2px;}
.mo-nota{color:var(--ink-muted);font-size:10.5px;}
body .wrap{max-width:1480px;}
body.mo-ancho .wrap{max-width:none;padding-left:24px;padding-right:24px;}
@media(min-width:881px){body.mo-ancho .grid{grid-template-columns:minmax(0,1fr) 340px;gap:18px;}}
.filtros select{max-width:340px;}
@media(min-width:881px){.panel{position:sticky;top:calc(var(--nav-h) + 56px);max-height:calc(100vh - var(--nav-h) - 72px);}}
`;
  (function () { const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st); })();

  let M = null;
  MO.render = function () {
    const cont = $('view-obras');
    if (!cont) return;
    if (typeof d3 === 'undefined') { cont.innerHTML = '<div class="vacio">No se pudo cargar d3 (vendor/d3-7.9.0).</div>'; return; }
    M = modelo();
    document.body.classList.toggle('mo-ancho', !!est.ancho);
    cont.innerHTML = controlesHtml(M);
    $('mo-saltos').value = String(est.saltos);
    conectarControles();
    dibujar();
  };

  let R = null;
  function dibujar() {
    R = recorte(M);
    const svg = d3.select('#mo-svg');
    svg.selectAll('*').remove();
    const box = $('mo-svg').getBoundingClientRect();
    const W = box.width || 900, H = box.height || 640;
    capa = svg.append('g');
    zoom = d3.zoom().scaleExtent([0.2, 6]).on('zoom', ev => { capa.attr('transform', ev.transform); etiquetas(ev.transform.k); });
    let movida = false;
    zoom.on('start', ev => { if (ev.sourceEvent) movida = true; });
    svg.call(zoom).on('dblclick.zoom', null);
    // encuadrar: cuando la simulación se asienta (y si no moviste la vista)
    const encuadrar = () => {
      if (movida || !nodos.length) return;
      const xs = nodos.map(n => n.x), ys = nodos.map(n => n.y), m = 40;
      const x0 = Math.min(...xs) - m, x1 = Math.max(...xs) + m, y0 = Math.min(...ys) - m, y1 = Math.max(...ys) + m;
      const k = Math.min(2, 0.95 * Math.min(W / (x1 - x0), H / (y1 - y0)));
      svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k));
    };
    svg.on('click', ev => { if (ev.target === svg.node()) { sel.clear(); marcar(); MO.panel(null); } });
    svg.append('defs').html('<marker id="mo-flecha" viewBox="0 0 6 6" refX="10" refY="3" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#60a5fa"/></marker>');

    // peso de cada obra: Cowork + diagonales + halladas. El tamaño va con
    // la raíz del peso relativo y tiene tope: 4 a 20 px de radio.
    const pesoObra = {};
    const sumar = (id, v) => { pesoObra[id] = (pesoObra[id] || 0) + v; };
    R.rels.forEach(r => { sumar(r.a, r.peso); sumar(r.b, r.peso); });
    R.diag.forEach(e => { const v = 1.5 * Math.log2(1 + e.lista.length) * 2; sumar(e.a, v); sumar(e.b, v); });
    R.hall.forEach(h => { sumar(h.a, 1); sumar(h.b, 1); });
    const maxPeso = Math.max(1, ...Object.values(pesoObra));
    const hallSet = new Set(); R.hall.forEach(h => { hallSet.add(h.a); hallSet.add(h.b); });
    const nodos = [...R.ids].map(id => {
      const o = M.porId[id], p = posiciones[id] || {};
      return { id, o, r: 4 + 16 * Math.sqrt((pesoObra[id] || 0) / maxPeso), x: p.x, y: p.y, fx: p.fx, fy: p.fy };
    });
    const idx = Object.fromEntries(nodos.map(n => [n.id, n]));
    const maxP = Math.max(1, ...R.rels.map(r => r.peso));
    const enlaces = R.rels.map(r => ({ source: r.a, target: r.b, tipo: 'cowork', r, w: r.peso / maxP }))
      .concat(R.diag.filter(e => e.a !== e.b).map(e => ({ source: e.a, target: e.b, tipo: 'diag', e, w: 1 })))
      .concat(R.hall.map(h => ({ source: h.a, target: h.b, tipo: 'hall', h, w: 0.5 })));

    const grado = {};
    enlaces.forEach(l => { grado[l.source] = (grado[l.source] || 0) + 1; grado[l.target] = (grado[l.target] || 0) + 1; });
    const lk = capa.append('g').selectAll('path').data(enlaces).join('path')
      .attr('class', d => 'mo-e ' + d.tipo)
      .attr('stroke', d => d.tipo === 'cowork' ? (est.color ? colorDim(d.r.dim) : NEUTRO) : null)
      .attr('stroke-width', d => d.tipo === 'diag' ? 0.8 + Math.log2(1 + d.e.lista.length) : d.tipo === 'hall' ? 1.3 : 0.6 + 2 * d.w)
      .attr('stroke-opacity', d => d.tipo === 'diag' ? 0.5 : d.tipo === 'hall' ? 0.8 : (est.color ? 0.25 + 0.45 * d.w : 0.14 + 0.3 * d.w))
      .attr('marker-end', d => d.tipo === 'diag' ? 'url(#mo-flecha)' : null);
    lk.append('title').text(d => d.tipo === 'diag'
      ? d.e.lista.length + ' diagonal(es): ' + [...new Set(d.e.lista.map(x => instrEtiqueta(x.instrumento)))].join(', ')
      : d.tipo === 'hall' ? 'hallada por la búsqueda (' + (d.h.palabra ? 'palabra «' + d.h.palabra + '»' : 'léxico compartido') + '): ' + titulo(d.h.a) + ' — ' + titulo(d.h.b)
      : titulo(d.r.a) + ' — ' + titulo(d.r.b) + ' · ' + d.r.dim + ' · peso ' + d.r.peso.toFixed(2));

    const nd = capa.append('g').selectAll('g').data(nodos).join('g')
      .attr('class', d => 'mo-n' + (d.id === est.foco ? ' foco' : '') + (d.fx != null ? ' fijo' : '') + (hallSet.has(d.id) ? ' hallada' : ''))
      .call(d3.drag()
        .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on('end', (ev, d) => { if (!ev.active) sim.alphaTarget(0); posiciones[d.id] = { x: d.x, y: d.y, fx: d.fx, fy: d.fy }; d3.select(ev.sourceEvent.target.parentNode).classed('fijo', true); }))
      .on('dblclick', (ev, d) => { ev.stopPropagation(); d.fx = d.fy = null; posiciones[d.id] = { x: d.x, y: d.y }; d3.select(ev.currentTarget).classed('fijo', false); sim.alpha(0.3).restart(); })
      .on('click', (ev, d) => {
        ev.stopPropagation();
        if (ev.shiftKey) { sel.has(d.id) ? sel.delete(d.id) : sel.add(d.id); }
        else { sel = new Set([d.id]); }
        marcar(); MO.panel(sel.size === 1 ? [...sel][0] : null);
      })
      .on('mouseenter', (ev, d) => { hoverId = d.id; marcar(); })
      .on('mouseleave', () => { hoverId = null; marcar(); });
    nd.append('circle').attr('r', d => d.r)
      .attr('fill', d => d.o.tipo_nodo === 'pdf' ? '#3a3a3a' : 'var(--mark)')
      .attr('fill-opacity', d => d.o.en_linea ? 1 : 0.45);
    nd.append('text').attr('dy', d => -d.r - 4).attr('text-anchor', 'middle')
      .text(d => { const t = d.o.titulo || d.id; return t.length > 28 ? t.slice(0, 27) + '…' : t; });

    const vecinosDe = {};
    enlaces.forEach(l => { const a = l.source.id || l.source, b = l.target.id || l.target; (vecinosDe[a] = vecinosDe[a] || new Set()).add(b); (vecinosDe[b] = vecinosDe[b] || new Set()).add(a); });

    sim = d3.forceSimulation(nodos)
      .force('link', d3.forceLink(enlaces).id(d => d.id)
        .distance(l => l.tipo === 'diag' ? 130 : l.tipo === 'hall' ? 110 : 170 - 90 * l.w)
        .strength(l => l.tipo === 'diag' ? 0.25 : l.tipo === 'hall' ? 0.4 : 0.12 + 0.4 * l.w))
      .force('carga', d3.forceManyBody().strength(-260))
      .force('choque', d3.forceCollide().radius(d => d.r + 8))
      .force('x', d3.forceX(W / 2).strength(0.05)).force('y', d3.forceY(H / 2).strength(0.06))
      .on('tick', () => {
        lk.attr('d', l => {
          const a = l.source, b = l.target, dx = b.x - a.x, dy = b.y - a.y, dr = Math.hypot(dx, dy) * (l.tipo === 'diag' ? 2.2 : 3);
          return l.tipo === 'diag' ? `M${a.x},${a.y}A${dr},${dr} 0 0,1 ${b.x},${b.y}` : `M${a.x},${a.y}L${b.x},${b.y}`;
        });
        nd.attr('transform', d => `translate(${d.x},${d.y})`);
      })
      .on('end', () => { nodos.forEach(n => { posiciones[n.id] = Object.assign(posiciones[n.id] || {}, { x: n.x, y: n.y }); }); encuadrar(); });
    setTimeout(encuadrar, 900);
    if (est.foco && idx[est.foco]) { const f = idx[est.foco]; f.fx = W / 2; f.fy = H / 2; }

    function marcar() {
      const activo = hoverId ? new Set([hoverId]) : sel;
      if (!activo.size) { nd.classed('mo-dim-apag', false); lk.classed('mo-dim-apag', false); }
      else {
        const soloEntre = !hoverId && sel.size > 1;
        const ok = new Set(activo);
        if (!soloEntre) activo.forEach(id => (vecinosDe[id] || new Set()).forEach(v => ok.add(v)));
        nd.classed('mo-dim-apag', d => !ok.has(d.id));
        lk.classed('mo-dim-apag', l => {
          const a = l.source.id, b = l.target.id;
          return soloEntre ? !(sel.has(a) && sel.has(b)) : !(activo.has(a) || activo.has(b));
        });
      }
      nd.classed('sel', d => sel.has(d.id));
      nd.select('text').attr('display', d => visibleEtiqueta(d) ? null : 'none');
      document.querySelectorAll('#mo-sueltas .mo-chip').forEach(c => c.classList.toggle('sel', sel.has(c.dataset.id)));
    }
    // etiquetas: con poco zoom, solo las ~18 obras de más peso (más las
    // elegidas, el foco y la que está bajo el mouse); de cerca, todas
    const top = new Set(nodos.slice().sort((a, b) => b.r - a.r).slice(0, 18).map(n => n.id));
    let zk = 1;
    const visibleEtiqueta = d => zk >= 1.5 || top.has(d.id) || d.id === est.foco || sel.has(d.id) || d.id === hoverId
      || (hoverId && (vecinosDe[hoverId] || new Set()).has(d.id));
    function etiquetas(k) { zk = k; nd.select('text').attr('display', d => visibleEtiqueta(d) ? null : 'none'); }
    etiquetas(1);
    MO._marcar = marcar;
    pintarSueltas();
    marcar();
    if (sel.size === 1) MO.panel([...sel][0]);
  }

  // Franja de sueltas: las que entran al sitio, con la búsqueda a mano; las
  // que no entran, aparte y tenues (esas pueden quedar sueltas).
  function pintarSueltas() {
    const cont = $('mo-sueltas');
    if (!cont) return;
    const dentro = R.sueltas.filter(id => entraAlSitio(M.porId[id])), fuera = R.sueltas.filter(id => !entraAlSitio(M.porId[id]));
    const ord = l => l.sort((a, b) => String(titulo(a)).localeCompare(String(titulo(b)), 'es'));
    const chip = (id, cl) => `<button class="mo-chip${cl}" data-id="${escHtml(id)}">${escHtml(titulo(id))}</button>`;
    if (!R.sueltas.length) { cont.innerHTML = est.foco ? '' : '<div class="mo-nota">Ninguna obra suelta: todas tienen al menos un vínculo a la vista.</div>'; return; }
    cont.innerHTML =
      (dentro.length ? `<div class="fila"><span class="cab">sueltas que entran al sitio (${dentro.length}):</span>${ord(dentro).map(id => chip(id, '')).join('')}
        <button class="mo-b" id="mo-conectar-todas" title="Para cada una, conecta las 2 obras del grupo con más léxico en común">conectar todas por léxico</button></div>` : '') +
      (fuera.length ? `<div class="fila"><span class="cab">no entran al sitio (${fuera.length}):</span>${ord(fuera).map(id => chip(id, ' fuera')).join('')}</div>` : '') +
      `<div class="mo-nota">Una obra queda suelta cuando no tiene diagonales ni relaciones del Cowork con las dimensiones prendidas. Elegila para buscarle relaciones.</div>`;
    cont.querySelectorAll('.mo-chip').forEach(c => c.addEventListener('click', ev => {
      if (ev.shiftKey) { sel.has(c.dataset.id) ? sel.delete(c.dataset.id) : sel.add(c.dataset.id); }
      else sel = new Set([c.dataset.id]);
      if (MO._marcar) MO._marcar();
      MO.panel(sel.size === 1 ? [...sel][0] : null);
    }));
    const b = $('mo-conectar-todas');
    if (b) b.addEventListener('click', async () => {
      b.disabled = true; b.textContent = 'buscando…';
      try { await conectarSueltas(dentro); } catch (e) { b.textContent = 'no se pudo: ' + e.message; return; }
      guardar(); MO.render();
    });
  }

  function conectarControles() {
    const re = () => { guardar(); dibujar(); };
    $('mo-buscar').addEventListener('change', e => {
      const o = M.obras.find(x => x.titulo === e.target.value || x.id === e.target.value);
      if (o) MO.enfocar(o.id); else if (!e.target.value) { est.foco = null; re(); }
    });
    $('mo-saltos').addEventListener('change', e => { est.saltos = +e.target.value; re(); });
    $('mo-todo').addEventListener('click', () => { est.foco = null; $('mo-buscar').value = ''; re(); });
    $('mo-k').addEventListener('input', e => { est.k = +e.target.value; $('mo-k-n').textContent = est.k; re(); });
    $('mo-ancho').addEventListener('click', () => { est.ancho = !est.ancho; guardar(); MO.render(); });
    $('mo-capas').addEventListener('toggle', e => { est._capasAbiertas = e.target.open; guardar(); });
    $('mo-c-diag').addEventListener('change', e => { est.capas.diag = e.target.checked; re(); });
    $('mo-c-hall').addEventListener('change', e => { est.capas.halladas = e.target.checked; re(); });
    $('mo-c-cowork').addEventListener('change', e => { est.capas.cowork = e.target.checked; re(); });
    $('mo-color').addEventListener('change', e => { est.color = e.target.checked; re(); });
    document.querySelectorAll('#view-obras [data-dim]').forEach(c => c.addEventListener('change', () => { est.dims[c.dataset.dim] = c.checked; re(); }));
    [['mo-g-texto', 'texto'], ['mo-g-pdf', 'pdf'], ['mo-g-fuera', 'fuera']].forEach(([id, g]) => $(id).addEventListener('change', e => { est.grupos[g] = e.target.checked; re(); }));
    $('mo-soltar').addEventListener('click', () => { posiciones = {}; re(); });
    if ($('mo-mostrar')) $('mo-mostrar').addEventListener('click', () => { est.ocultas = []; guardar(); MO.render(); });
  }

  MO.enfocar = function (id) {
    est.foco = id; sel = new Set(); guardar();
    if ($('mo-buscar') && M.porId[id]) $('mo-buscar').value = M.porId[id].titulo;
    dibujar();
    MO.panel(id);
  };
  MO.apagar = function (id) {
    if (!est.ocultas.includes(id)) est.ocultas.push(id);
    sel.delete(id); if (est.foco === id) est.foco = null;
    guardar(); MO.render(); MO.panel(null);
  };

  /* ── buscador de relaciones ──
     Compara obras por su léxico: las familias de palabras de pulenta
     (parientes.json, contadas en lo que está en línea). Cada obra es un
     vector de familias pesado por tf-idf (las familias que están en todas
     las obras casi no cuentan); la afinidad entre dos obras es el coseno.
     Las obras que parientes.json todavía no cuenta (recién subidas) se
     leen en el momento: el texto de su página, o el .txt de su PDF en
     Archivo/, y cada palabra se lleva a su familia con el mismo índice.
     La búsqueda por palabra lleva la palabra a su familia y lista las
     obras que la usan, de más a menos; si no tiene familia, la busca entre
     las claves de los pasajes de la superficie relacional. No se escribe
     nada en el repo. */
  const B = { listo: null, par: null, N: 0, df: null, vec: {}, norma: {}, pend: {} };
  const TOKEN = /[\p{L}]+(?:-[\p{L}]+)*/gu;
  function cargarBuscador() {
    if (B.listo) return B.listo;
    B.listo = leerJSON('parientes.json').then(par => {
      B.par = par; B.N = par.o.length;
      const cuentas = par.o.map(() => new Map());
      par.f.forEach((fam, fi) => Object.values(fam.m || {}).forEach(m => (m.g || []).forEach(([oi, n]) => {
        const c = cuentas[oi]; if (c) c.set(fi, (c.get(fi) || 0) + n);
      })));
      B.df = new Float64Array(par.f.length);
      cuentas.forEach(c => c.forEach((n, fi) => { B.df[fi]++; }));
      par.o.forEach(([slug], oi) => fijarVector(slug, cuentas[oi]));
      return B;
    }).catch(e => { B.listo = null; throw e; });
    return B.listo;
  }
  function fijarVector(slug, cuenta) {
    const v = new Map(); let s = 0;
    cuenta.forEach((n, fi) => {
      const idf = Math.log((B.N + 1) / (B.df[fi] + 1));
      if (idf <= 0) return;
      const w = (1 + Math.log(n)) * idf; v.set(fi, w); s += w * w;
    });
    B.vec[slug] = v; B.norma[slug] = Math.sqrt(s) || 1;
  }
  // El texto sale de la fuente (obras/<slug>.json): las páginas obras/*.html
  // son un intermedio que se regenera y no se versiona.
  async function textoDeObra(o) {
    const slug = o._file ? o._file.replace(/\.html$/, '') : o.id;
    const r = await fetch('obras/' + encodeURIComponent(slug) + '.json', { cache: 'no-store' });
    // páginas con nombre de título (beta, pop) sin fuente de ese nombre: el corpus trae los capítulos
    if (!r.ok && !(o._chapters && o._chapters.length)) throw new Error('obras/' + slug + '.json: HTTP ' + r.status);
    const d = r.ok ? await r.json() : { chapters: o._chapters };
    if (Array.isArray(d.chapters) && d.chapters.length) {
      const div = document.createElement('div');
      return d.chapters.map(c => { div.innerHTML = c.body || ''; return div.textContent || ''; }).join('\n');
    }
    const archivo = d.pdf && (d.pdf.texto || d.pdf.archivo);
    if (archivo) {
      const nombre = String(archivo).replace(/\.(pdf|txt)$/i, '.txt');
      const t = await fetch('Archivo/' + encodeURIComponent(nombre), { cache: 'no-store' });
      if (t.ok) return (await t.text()).replace(/<<<PAGE \d+>>>/g, '\n');
    }
    return '';
  }
  async function vectorDe(id) {
    await cargarBuscador();
    if (B.vec[id]) return B.vec[id];
    if (!B.pend[id]) B.pend[id] = (async () => {
      const texto = await textoDeObra(M.porId[id] || { id });
      const cuenta = new Map();
      (texto.toLowerCase().match(TOKEN) || []).forEach(w => { const u = B.par.u[w]; if (u) cuenta.set(u[0], (cuenta.get(u[0]) || 0) + 1); });
      fijarVector(id, cuenta);
      return B.vec[id];
    })();
    return B.pend[id];
  }
  // una familia se nombra por su miembro más usado, no por la raíz truncada
  function nombreFamilia(fi) { const f = B.par.f[fi]; return (f.s && f.s[0] && f.s[0][0]) || f.r; }
  function coseno(a, b) {
    const va = B.vec[a], vb = B.vec[b]; if (!va || !vb) return { s: 0, fam: [] };
    const [chica, grande] = va.size < vb.size ? [va, vb] : [vb, va];
    let s = 0; const aporte = [];
    chica.forEach((w, fi) => { const x = grande.get(fi); if (x) { s += w * x; aporte.push([fi, w * x]); } });
    aporte.sort((x, y) => y[1] - x[1]);
    return { s: s / (B.norma[a] * B.norma[b]), fam: aporte.slice(0, 5).map(([fi]) => nombreFamilia(fi)) };
  }
  // candidatas para una obra: las del grupo (con algún vínculo) primero
  async function candidatas(id, n) {
    await vectorDe(id);
    if (!B.vec[id] || !B.vec[id].size) return [];
    const enGrupo = R ? R.ids : new Set();
    const lista = M.obras.filter(o => o.id !== id && obraVisibleBase(o) && B.vec[o.id])
      .map(o => Object.assign({ id: o.id, enGrupo: enGrupo.has(o.id) }, coseno(id, o.id)))
      .filter(c => c.s > 0).sort((x, y) => y.s - x.s);
    return lista.slice(0, n || 10);
  }
  async function porPalabra(id, palabra) {
    await cargarBuscador();
    const w = palabra.trim().toLowerCase();
    const u = B.par.u[w];
    if (!u) return porPalabraEnPasajes(id, w);
    const fam = B.par.f[u[0]];
    const cuenta = {};
    Object.values(fam.m || {}).forEach(m => (m.g || []).forEach(([oi, n]) => { const s = B.par.o[oi][0]; cuenta[s] = (cuenta[s] || 0) + n; }));
    await vectorDe(id).catch(() => null);
    const propia = cuenta[id] || (B.vec[id] && B.vec[id].has(u[0]) ? '·' : 0);
    const lista = Object.entries(cuenta).filter(([s]) => s !== id && M.porId[s] && obraVisibleBase(M.porId[s]))
      .sort((x, y) => y[1] - x[1]).slice(0, 12).map(([s, n]) => ({ id: s, n }));
    return { familia: nombreFamilia(u[0]), miembros: Object.keys(fam.m || {}).slice(0, 6), propia, lista, fi: u[0] };
  }
  // Palabras sin familia (las familias de pulenta solo juntan palabras con
  // derivados): se buscan en la superficie relacional, entre las claves de
  // cada pasaje (sus 20 lemas de más tf-idf). Pesa ~6 MB: se lee una vez,
  // solo si hace falta. Devuelve las obras con más pasajes donde la palabra
  // es clave, con el fragmento del pasaje donde más pesa.
  const SUP = { listo: null };
  function cargarSuperficie() {
    if (!SUP.listo) SUP.listo = Promise.all(['lexico', 'pasajes', 'perfil'].map(n => leerJSON('matriz/superficie/' + n + '.json')))
      .then(([lex, pas, perfil]) => {
        SUP.claves = new Map(); lex.claves.forEach((c, i) => SUP.claves.set(c, i));
        SUP.formas = new Map(); (lex.forma || []).forEach((f, i) => { if (f && !SUP.formas.has(f)) SUP.formas.set(f, i); });
        const taller = Object.fromEntries(Object.entries(perfil.obras || {}).map(([k, v]) => [k, v.taller || k]));
        SUP.pasajes = pas.map(x => Object.assign({ obra: taller[x.o] || x.o }, x));
        return SUP;
      }).catch(e => { SUP.listo = null; throw e; });
    return SUP.listo;
  }
  async function porPalabraEnPasajes(id, w) {
    await cargarSuperficie();
    const ci = SUP.claves.has(w) ? SUP.claves.get(w) : SUP.formas.get(w);
    if (ci == null) return { familia: null, lista: [] };
    const porObra = {};
    SUP.pasajes.forEach(x => {
      for (let i = 0; i < x.k.length; i += 2) if (x.k[i] === ci) {
        const r = porObra[x.obra] = porObra[x.obra] || { n: 0, peso: 0, t: '' };
        r.n++; if (x.k[i + 1] > r.peso) { r.peso = x.k[i + 1]; r.t = x.t; }
        break;
      }
    });
    const lista = Object.entries(porObra).filter(([s]) => s !== id && M.porId[s] && obraVisibleBase(M.porId[s]))
      .sort((x, y) => y[1].n - x[1].n || y[1].peso - x[1].peso).slice(0, 12)
      .map(([s, r]) => ({ id: s, n: r.n, t: r.t, pasajes: true }));
    const clave = [...SUP.claves.entries()].find(([, i]) => i === ci)[0];
    return { familia: clave, superficie: true, miembros: [], propia: porObra[id] ? porObra[id].n : 0, lista };
  }
  function hallada(a, b) { return est.halladas.find(h => (h.a === a && h.b === b) || (h.a === b && h.b === a)); }
  function conectar(a, b, datos) {
    if (hallada(a, b)) return;
    est.halladas.push(Object.assign({ a, b, fecha: new Date().toISOString().slice(0, 10) }, datos));
  }
  function desconectar(a, b) { est.halladas = est.halladas.filter(h => !((h.a === a && h.b === b) || (h.a === b && h.b === a))); }
  async function conectarSueltas(ids) {
    for (const id of ids) {
      let cs = [];
      try { cs = await candidatas(id, 20); } catch (e) { continue; }
      cs.filter(c => c.enGrupo).slice(0, 2).forEach(c => conectar(id, c.id, { afinidad: +c.s.toFixed(3), familias: c.fam, fuente: 'léxico' }));
    }
  }

  // ── panel de la obra elegida ──
  MO.panel = function (id) {
    const p = $('detail-panel');
    if (!id) {
      p.innerHTML = sel.size > 1
        ? `<div class="ph-title">${sel.size} obras elegidas</div><dd style="color:var(--ink-muted)">Se ve solo lo que pasa entre ellas. Mayús+clic suma o saca; clic en el fondo suelta.</dd>`
        : `<div class="ph-title">Elegí una obra</div><dd style="color:var(--ink-muted)">Buscala arriba o hacé clic en un nodo. Azul: escritas; gris: PDF; más tenue: no publicadas. El tamaño es cuánto se relaciona. Las sueltas están debajo del grafo.</dd>`;
      return;
    }
    const o = M.porId[id]; if (!o) return;
    const rels = M.rels.filter(r => r.a === id || r.b === id).sort((x, y) => y.peso - x.peso);
    const dg = M.diag.filter(e => e.a === id || e.b === id);
    const hs = est.halladas.filter(h => h.a === id || h.b === id);
    const props = (M.props[id] || []).slice().sort((x, y) => (y.puntaje_total || y.total || 0) - (x.puntaje_total || x.total || 0));
    const suelta = R && R.sueltas.includes(id);
    p.innerHTML = `<div class="ph-title">${escHtml(o.titulo)}</div>
      <dd>${o.tipo_nodo === 'pdf' ? 'PDF' : 'escrita'}${o.categoria ? ' · ' + escHtml(o.categoria) : ''}${o.en_linea ? '' : ' · no publicada'}${o._file ? ` — <a href="obras/${escHtml(o._file)}" target="_blank">abrir →</a>` : ''}</dd>
      ${suelta ? `<dd class="mo-nota">${entraAlSitio(o) ? 'Suelta: no tiene vínculos a la vista. Buscale relaciones abajo.' : 'Suelta, y no entra al sitio: puede quedar así.'}</dd>` : ''}
      <div class="mo-acc">
        ${est.foco === id || suelta ? '' : `<button class="mo-b" data-mo="foco">centrar acá</button>`}
        <button class="mo-b" data-mo="apagar">apagar esta obra</button>
      </div>
      <dt>buscar relaciones</dt>
      <div class="mo-busca"><input id="mo-palabra" placeholder="una palabra: busca su familia…" autocomplete="off"><button class="mo-b" data-mo="palabra">buscar</button></div>
      <button class="mo-b" data-mo="lexico">obras con más léxico en común</button>
      <div id="mo-resultado"></div>
      ${hs.length ? `<dt>halladas por la búsqueda (${hs.length})</dt>` + hs.map(h => {
        const otra = h.a === id ? h.b : h.a;
        return `<div class="mo-cand"><button class="mo-b" data-quitar="${escHtml(otra)}">quitar</button><span class="t" data-ir="${escHtml(otra)}">${escHtml(titulo(otra))}</span>
          <div class="fam">${h.palabra ? 'palabra «' + escHtml(h.palabra) + '»' : 'léxico'}${h.afinidad != null ? ' · afinidad ' + h.afinidad.toFixed(2) : ''}${(h.familias || []).length ? ' · ' + escHtml(h.familias.join(', ')) : ''}</div></div>`;
      }).join('') + '<dd class="mo-nota">Las propone la matriz, no vos: se guardan solo en este navegador.</dd>' : ''}
      <dt>tus diagonales (${dg.reduce((a, e) => a + e.lista.length, 0)})</dt>
      ${dg.length ? dg.map(e => `<div class="det-row">${e.a === id ? '→ ' + escHtml(titulo(e.b)) : '← ' + escHtml(titulo(e.a))} <span style="color:var(--ink-muted)">· ${e.lista.length > 1 ? e.lista.length + ' · ' : ''}${escHtml([...new Set(e.lista.map(x => instrEtiqueta(x.instrumento)))].join(', '))}</span></div>`).join('') : '<dd style="color:var(--ink-muted)">ninguna todavía</dd>'}
      <dt>relaciones del Cowork (${rels.length})</dt>
      <div class="mo-lista">${rels.slice(0, 15).map(r => {
        const otra = r.a === id ? r.b : r.a;
        const ev = ((r.evidencia || {}).criterios || []).slice(0, 2).map(c => c.criterio).filter(Boolean).join(' · ');
        return `<div class="det-row" data-ir="${escHtml(otra)}"><i style="display:inline-block;width:9px;height:3px;background:${colorDim(r.dim)};margin-right:6px;vertical-align:middle"></i>${escHtml(titulo(otra))} <span style="color:var(--ink-muted)">· ${r.peso.toFixed(2)} · ${escHtml(r.dim)}</span>${ev ? `<div style="color:var(--ink-ghost);font-size:10px">${escHtml(ev)}</div>` : ''}</div>`;
      }).join('')}${rels.length > 15 ? `<dd style="color:var(--ink-muted)">y ${rels.length - 15} más</dd>` : ''}</div>
      <dt>propuestas del motor (${props.length})</dt>
      ${props.length ? props.slice(0, 8).map(pr => {
        const otro = pr.origen.sitio === id ? pr.destino : pr.origen;
        return `<div class="det-row">${escHtml(instrEtiqueta(pr.instrumento))} → ${escHtml(titulo(otro.sitio))}${otro.pdf_pagina != null ? ', p. ' + otro.pdf_pagina : ''}</div>`;
      }).join('') + `<dd style="color:var(--ink-muted)">Se aceptan o rechazan en el taller.</dd>` : '<dd style="color:var(--ink-muted)">ninguna</dd>'}`;
    const ir = root => root.querySelectorAll('[data-ir]').forEach(el => el.addEventListener('click', () => MO.enfocar(el.dataset.ir)));
    ir(p);
    const b = p.querySelector('[data-mo="foco"]'); if (b) b.addEventListener('click', () => MO.enfocar(id));
    p.querySelector('[data-mo="apagar"]').addEventListener('click', () => MO.apagar(id));
    p.querySelectorAll('[data-quitar]').forEach(x => x.addEventListener('click', () => { desconectar(id, x.dataset.quitar); guardar(); MO.render(); MO.panel(id); }));

    const res = $('mo-resultado');
    const filaCand = (otra, linea, datos) => {
      const ya = hallada(id, otra);
      return `<div class="mo-cand"><button class="mo-b" data-con="${escHtml(otra)}"${ya ? ' disabled' : ''}>${ya ? 'conectada' : 'conectar'}</button><span class="t" data-ir="${escHtml(otra)}">${escHtml(titulo(otra))}</span><div class="fam">${linea}</div></div>`;
    };
    const conectarBotones = (mapa) => res.querySelectorAll('[data-con]').forEach(x => x.addEventListener('click', () => {
      conectar(id, x.dataset.con, mapa[x.dataset.con]); guardar(); MO.render(); sel = new Set([id]); MO.panel(id);
    }));
    const esperar = t => { res.innerHTML = `<dd class="mo-nota">${t}</dd>`; };
    p.querySelector('[data-mo="lexico"]').addEventListener('click', async () => {
      esperar('leyendo el léxico…');
      try {
        const cs = await candidatas(id, 10);
        if (!cs.length) { esperar('No hay léxico contado para esta obra (ni en parientes.json ni en su página).'); return; }
        const mapa = {};
        cs.forEach(c => { mapa[c.id] = { afinidad: +c.s.toFixed(3), familias: c.fam, fuente: 'léxico' }; });
        res.innerHTML = cs.map(c => filaCand(c.id, `afinidad ${c.s.toFixed(2)}${c.enGrupo ? '' : ' · también suelta'} · ${escHtml(c.fam.join(', '))}`)).join('')
          + '<dd class="mo-nota">Afinidad: coseno entre los léxicos (familias de palabras, pesadas por lo raras que son en el corpus).</dd>';
        ir(res); conectarBotones(mapa);
      } catch (e) { esperar('No se pudo: ' + escHtml(e.message)); }
    });
    const buscarPalabra = async () => {
      const w = $('mo-palabra').value; if (!w.trim()) return;
      esperar('buscando «' + escHtml(w) + '»…');
      try {
        const r = await porPalabra(id, w);
        if (!r.familia) { esperar('«' + escHtml(w) + '» no está ni en las familias de pulenta ni entre las claves de la superficie. Probá con otra forma (el infinitivo, el singular).'); return; }
        const mapa = {};
        r.lista.forEach(x => { mapa[x.id] = { familias: [r.familia], palabra: w.trim().toLowerCase(), fuente: 'palabra' }; });
        res.innerHTML = (r.superficie
            ? `<dd class="mo-nota">«${escHtml(r.familia)}» como clave de pasajes (superficie relacional)${r.propia ? ' · acá en ' + r.propia : ' · en esta obra no es clave'}</dd>`
            : `<dd class="mo-nota">familia «${escHtml(r.familia)}» (${escHtml(r.miembros.join(', '))})${r.propia ? '' : ' · esta obra no la usa'}</dd>`)
          + (r.lista.length ? r.lista.map(x => filaCand(x.id, x.pasajes
              ? x.n + ' pasaje' + (x.n === 1 ? '' : 's') + (x.t ? ` · <i>«${escHtml(x.t.slice(0, 110))}…»</i>` : '')
              : x.n + ' aparicion' + (x.n === 1 ? '' : 'es'))).join('') : '<dd class="mo-nota">Ninguna otra obra la usa.</dd>');
        ir(res); conectarBotones(mapa);
      } catch (e) { esperar('No se pudo: ' + escHtml(e.message)); }
    };
    p.querySelector('[data-mo="palabra"]').addEventListener('click', buscarPalabra);
    $('mo-palabra').addEventListener('keydown', e => { if (e.key === 'Enter') buscarPalabra(); });
  };
})();
