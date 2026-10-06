/* diagonal.js — la diagonal como objeto propio (no pertenece a las obras:
   las atraviesa). Lo usan obra-template.html y pdf-post-template.html.

   Qué hace:
   - Tarjeta del ala (hover / clic): relación · instrumento › subcategoría ·
     cluster (por ahora, los nodos); tema + sinopsis; nodos agregables y
     concepto (#dg-…) para la autora.
   - Expandir: origen · diagonal · destino. A los lados, la oración de la
     cita con una antes y una después, dentro del párrafo (≈300 caracteres,
     con margen para no cortar una oración). En el centro, el emergente con
     sus vínculos (una expresión que remite a un pasaje de un lado), las
     anclas de diagonal (una diagonal que sale de la diagonal) y las notas.
   - Lo que carga la autora desde acá queda en diagonales.json (no en las
     obras): en su máquina por servidor.py (/api/diagonales), en la web con
     el token (autor.js).

   La página que lo usa define, antes de abrir Expandir:
     window.DIAG_HOST = {
       par(origenId, destinoId) → Promise<{ o: lado, d: lado }>
         lado = { parrafo: texto plano del párrafo (o página) de la cita,
                  frag: la cita, etiqueta: 'obra · capítulo', orden: '' }
     }
   y usa las globales ACCIONES e irAAccion(id) que ya tiene. */
(function () {
  'use strict';
  const DG = window.DG = {};
  const PREFIJO = 'dg-';
  const yo = document.currentScript;
  const BASE = new URL('.', yo ? yo.src : location.href).href;
  let DATOS = { conceptos: {}, diagonales: {} };
  let cargando = null;
  const LABELS = {};

  const CSS = `
.dg-card .diag-dato{display:grid;grid-template-columns:92px 1fr;gap:8px;margin:0 0 7px;font-family:var(--font-mono);font-size:10.5px;line-height:1.45;}
.dg-card .diag-k,.dg-autor .diag-k{color:var(--ink-ghost);text-transform:uppercase;letter-spacing:.12em;font-size:9px;padding-top:2px;}
.dg-card .diag-v{color:var(--ink);} .dg-card .diag-v small{color:var(--ink-muted);font-size:inherit;}
.diag-nodos span+span::before{content:' · ';color:var(--ink-ghost);} .diag-nodos{color:var(--emergente);}
.dg-vacia-rot{font-family:var(--font-mono,monospace);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-ghost);margin:4px 0 8px;}
.dg-concepto{font-family:var(--font-mono);color:var(--mark-lt);}
.dg-tema{border:1px solid var(--rule);border-radius:3px;padding:10px 12px;margin:12px 0 14px;background:color-mix(in oklab,var(--page) 70%,transparent);}
.dg-tema-t{font-style:italic;font-weight:500;font-size:16px;line-height:1.3;color:var(--ink);margin-bottom:6px;}
.dg-tema-s{font-size:14px;line-height:1.55;color:var(--ink-soft);} .dg-tema-s p{margin:0 0 .6em;} .dg-tema-s p:last-child{margin:0;}
.dg-autor{border-top:1px dashed var(--rule);margin:10px 0 12px;padding-top:8px;font-family:var(--font-mono);font-size:10.5px;}
.dg-autor-fila{display:grid;grid-template-columns:92px 1fr;gap:8px;align-items:center;margin-bottom:6px;}
.dg-chips{display:flex;flex-wrap:wrap;gap:4px;align-items:center;}
.dg-chip{display:inline-flex;align-items:center;gap:2px;border:1px solid var(--rule);border-radius:9px;padding:0 3px 0 8px;color:var(--emergente);}
.dg-chip button{background:none;border:0;color:var(--ink-muted);cursor:pointer;font-size:12px;}
.dg-autor input{background:transparent;border:0;border-bottom:1px dotted var(--ink-ghost);color:var(--ink);font:inherit;min-width:90px;flex:1;padding:2px 0;}
.dg-conc-in{display:flex;align-items:center;color:var(--mark-lt);}
.dg-ir-diag{margin-left:14px;} .dg-ir-leer{margin-left:0;}
html.modo-autor .dg-card:has(.dg-autor) .diag-dato.dg-lector{display:none;}
.dg-hacia{color:var(--ink-ghost);margin-right:2px;}
.dg-leer-btn{margin-left:14px;}
.dg-leer{margin:12px 0 4px;border-top:1px solid var(--rule);padding-top:10px;}
.dg-leer-n{font-family:var(--font-mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--mark-lt);margin-bottom:6px;}
.dg-leer-t{font-size:14px;line-height:1.55;color:var(--ink-soft);font-style:italic;margin:0 0 10px;}
#lectura-modal-body .dg-leer-t{font-size:14px;line-height:1.55;text-align:left;}
.dg-grafo{width:100%;height:auto;display:block;margin:4px 0 6px;}
.dg-grafo .isla{fill:color-mix(in oklab,var(--ink) 5%,transparent);stroke:var(--rule);}
.dg-grafo .isla-t{fill:var(--ink-muted);font-family:var(--font-mono);font-size:8.5px;}
.dg-grafo .arista{stroke:var(--ink-ghost);stroke-width:1;fill:none;}
.dg-grafo .arista.esta{stroke:var(--mark);stroke-width:2;}
.dg-grafo .nodo{fill:var(--emergente);} .dg-grafo .nodo.esta{fill:var(--mark);}
.dg-grafo .nodo.ir{cursor:pointer;}
.dg-leer-pie{font-family:var(--font-mono);font-size:9.5px;color:var(--ink-muted);}
#dg-aviso{position:fixed;left:50%;bottom:18px;transform:translate(-50%,20px);opacity:0;transition:.2s;z-index:200;background:var(--page);border:1px solid var(--rule);padding:8px 14px;border-radius:3px;font-family:var(--font-mono);font-size:11px;color:var(--ink);pointer-events:none;max-width:90vw;}
#dg-aviso.open{opacity:1;transform:translate(-50%,0);}
.dgx{position:fixed;inset:0;z-index:120;background:rgba(0,0,0,.72);display:none;align-items:center;justify-content:center;padding:16px;}
.dgx.open{display:flex;}
.dgx-ventana{position:relative;background:var(--page,var(--bg));border:1px solid var(--rule);border-radius:6px;width:min(1320px,100%);max-height:calc(100vh - 32px);display:flex;flex-direction:column;box-shadow:0 30px 90px rgba(0,0,0,.6);}
.dgx-cab{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--rule);font-family:var(--font-mono);font-size:11px;color:var(--ink-soft);}
.dgx-cab-der{display:flex;gap:16px;align-items:center;}
.dgx-tg{display:flex;gap:6px;align-items:center;cursor:pointer;font-size:10px;letter-spacing:.08em;text-transform:uppercase;}
.dgx-cerrar,.dgx-x,.dgx-mas{background:none;border:1px solid var(--rule);color:var(--ink-muted);font-family:var(--font-mono);font-size:10px;padding:3px 8px;border-radius:2px;cursor:pointer;}
.dgx-cuerpo{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr) minmax(0,1fr);overflow:auto;flex:1;min-height:0;}
.dgx-lado,.dgx-centro{padding:18px 20px;border-right:1px solid var(--rule);overflow:auto;}
.dgx-cuerpo > :last-child{border-right:0;}
.dgx-r{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:6px;}
.dgx-r-diag{color:var(--mark);}
.dgx-et{font-style:italic;font-size:14px;color:var(--ink);margin-bottom:6px;}
.dgx-orden{display:inline-block;margin:0 0 10px;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);border:1px solid var(--rule);border-radius:2px;padding:2px 6px;font-family:var(--font-mono);}
.dgx-p{font-size:15.5px;line-height:1.62;text-align:justify;hyphens:auto;color:var(--ink-soft);margin:6px 0 14px;}
.dgx-orden[hidden]{display:none;}
.dgx-cargando{font-family:var(--font-mono);font-size:11px;color:var(--ink-muted);font-style:normal;}
.dg-cita{color:var(--ink);background:color-mix(in oklab,var(--mark) 10%,transparent);border-radius:2px;}
.dgx-centro .diag-dato{display:grid;grid-template-columns:92px 1fr;gap:8px;margin:0 0 6px;font-family:var(--font-mono);font-size:10.5px;}
.dgx-centro .diag-k{color:var(--ink-ghost);text-transform:uppercase;letter-spacing:.12em;font-size:9px;padding-top:2px;}
.dgx-centro .diag-v{color:var(--ink);} .dgx-centro .diag-v small{color:var(--ink-muted);font-size:inherit;}
.dgx-titulo{font-style:italic;font-weight:500;font-size:19px;line-height:1.25;margin:12px 0 8px;color:var(--ink);}
.dgx-em{font-size:15.5px;line-height:1.62;font-style:italic;color:var(--ink);text-align:justify;hyphens:auto;margin-top:10px;}
.dgx-em p{margin:0 0 .8em;}
.dg-vin{cursor:pointer;border-bottom:1px dashed var(--emergente);}
.dg-vin.activa,.dg-vin:hover{background:color-mix(in oklab,var(--emergente) 18%,transparent);}
.dg-anc{cursor:pointer;border-bottom:1px solid var(--mark);} .dg-anc::after{content:'↗';font-size:.7em;color:var(--mark);margin-left:1px;}
.dg-anc.activa,.dg-anc:hover{background:color-mix(in oklab,var(--mark) 16%,transparent);}
.dg-refto{color:var(--ink);background:color-mix(in oklab,var(--emergente) 24%,transparent);box-shadow:inset 0 -1px 0 var(--emergente);}
.dg-comun{text-decoration:underline dotted var(--violet,#a78bfa);text-underline-offset:3px;}
.dgx-glosa{display:none;margin:4px 0 14px;border-left:2px solid var(--emergente);padding:6px 0 6px 12px;font-size:13.5px;line-height:1.5;color:var(--ink-soft);}
.dgx-glosa.open{display:block;}
.dgx-notas{margin-top:18px;border-top:1px solid var(--rule);padding-top:12px;}
.dgx-nota{position:relative;font-size:13.5px;line-height:1.5;color:var(--ink-soft);border-left:2px solid var(--green,#4ade80);padding:2px 26px 2px 10px;margin-bottom:10px;}
.dgx-nota p{margin:0 0 .4em;} .dgx-nota-f{font-family:var(--font-mono);font-size:9px;color:var(--ink-ghost);}
.dgx-nota .dgx-x{position:absolute;right:0;top:0;padding:0 5px;}
.dgx-nota-nueva{display:flex;flex-direction:column;gap:6px;margin-top:8px;}
.dgx-nota-nueva textarea{min-height:56px;background:transparent;border:1px solid var(--rule);color:var(--ink);font:inherit;font-size:13.5px;padding:6px 8px;resize:vertical;}
.dgx-nota-nueva button,.dgx-herr button{align-self:flex-start;background:var(--mark);color:var(--bg);border:0;font-family:var(--font-mono);font-size:10px;letter-spacing:.06em;padding:4px 9px;border-radius:2px;cursor:pointer;}
.dgx-herr{position:fixed;z-index:130;display:flex;gap:6px;}
.dgx-herr[hidden]{display:none;}
.dgx-vacio{color:var(--ink-muted);font-style:normal;font-family:var(--font-mono);font-size:11px;}
.dgx-pie{padding:8px 16px;border-top:1px solid var(--rule);font-family:var(--font-mono);font-size:10.5px;color:var(--ink-soft);min-height:14px;}
#dgx-elegir{position:absolute;inset:48px 10% 40px;background:var(--page,var(--bg));border:1px solid var(--rule);box-shadow:0 20px 60px rgba(0,0,0,.6);padding:14px;display:flex;flex-direction:column;gap:8px;z-index:3;}
#dgx-elegir[hidden]{display:none;}
#dgx-buscar{background:transparent;border:1px solid var(--rule);color:var(--ink);padding:6px 8px;font:inherit;}
#dgx-lista{overflow:auto;flex:1;display:flex;flex-direction:column;gap:2px;}
#dgx-lista button{text-align:left;background:none;border:0;border-bottom:1px solid var(--rule);color:var(--ink-soft);padding:6px 4px;cursor:pointer;font-size:13px;}
#dgx-lista button:hover{color:var(--ink);background:color-mix(in oklab,var(--mark) 8%,transparent);}
#dgx-lista b{font-family:var(--font-mono);font-size:10px;color:var(--mark-lt);font-weight:400;margin-right:6px;}
.dgp-cab{border:1px solid var(--rule);border-left:2px solid var(--mark);padding:12px 14px;margin:-40px 0 36px;font-family:var(--font-mono);font-size:10.5px;}
.dgp-cab .diag-dato{display:grid;grid-template-columns:130px 1fr;gap:8px;margin:0 0 5px;}
.dgp-cab .diag-k{color:var(--ink-ghost);text-transform:uppercase;letter-spacing:.12em;font-size:9px;padding-top:2px;}
.dgp-cab .diag-v{color:var(--ink);} .dgp-cab small{color:var(--ink-muted);font-size:inherit;}
.dgp-id{color:var(--mark-lt);font-size:12px;letter-spacing:.06em;margin-bottom:8px;}
.dgp-n{color:var(--ink-muted);font-size:9.5px;margin-top:6px;}
.dgp-alas .dgp-r{font-family:var(--font-mono);font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-muted);margin:14px 0 8px;}
.dgp-alas .dgp-lado{color:var(--mark);margin-top:0;}
.dgp-cita{border-left:2px solid var(--rule);padding:2px 0 2px 10px;margin-bottom:14px;transition:background .3s;}
.dgp-cita.base{border-left-color:var(--mark);}
.dgp-cita.activa{background:color-mix(in oklab,var(--emergente) 16%,transparent);border-left-color:var(--emergente);}
.dgp-frag{font-style:italic;font-size:14px;line-height:1.5;color:var(--ink-soft);}
.dgp-cita.base .dgp-frag{color:var(--ink);}
.dgp-meta{font-family:var(--font-mono);font-size:9.5px;color:var(--ink-muted);margin-top:4px;} .dgp-meta small{font-size:inherit;}
.dgp-orden{text-transform:uppercase;letter-spacing:.08em;}
body.dgp-vinculando .dgp-cita{cursor:crosshair;outline:1px dashed var(--emergente);outline-offset:2px;}
#text-body .dg-vin{cursor:pointer;border-bottom:1px dashed var(--emergente);}
#text-body .dg-vin.activa{background:color-mix(in oklab,var(--emergente) 18%,transparent);}
@media (max-width:900px){.dgx-cuerpo{grid-template-columns:1fr;}.dgx-lado,.dgx-centro{border-right:0;border-bottom:1px solid var(--rule);}.dgx{padding:0;}.dgx-ventana{max-height:100vh;height:100%;border-radius:0;}}
`;
  (function () { const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st); })();

  const esc = P314.esc;
  const parrafos = t => String(t || '').split(/\n+/).filter(x => x.trim()).map(x => '<p>' + esc(x) + '</p>').join('');
  const nuevoId = p => p + Math.random().toString(36).slice(2, 9);
  DG.slug = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  DG.clave = (a, b) => [a, b].sort().join('~');
  const autor = () => !!(window.P314B && window.P314B.autor);
  const acciones = () => (typeof ACCIONES !== 'undefined' ? ACCIONES : {});

  // ── datos ──
  function normalizar(d) {
    d = d && typeof d === 'object' ? d : {};
    d.conceptos = d.conceptos || {};
    d.diagonales = d.diagonales || {};
    return d;
  }
  DG.cargar = function () {
    if (cargando) return cargando;
    const P = window.P314B;
    const leerRepo = (P && P.modo === 'web' && P.leerArchivo)
      ? P.listo.then(ok => ok ? P.leerArchivo('diagonales.json') : null).catch(() => null)
      : Promise.resolve(null);
    cargando = leerRepo.then(txt => txt ? JSON.parse(txt) : fetch(BASE + 'diagonales.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : {}))
      .catch(() => ({})).then(d => { DATOS = normalizar(d); return DATOS; });
    fetch(BASE + 'subgrafo.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : {}).then(s => {
      (s.instrumentos || []).forEach(i => { LABELS[i.id] = i.label; });
    }).catch(() => {});
    return cargando;
  };
  DG.datos = () => DATOS;
  function reg(a, b, crear) {
    const k = DG.clave(a, b);
    if (!DATOS.diagonales[k] && crear) DATOS.diagonales[k] = {};
    return DATOS.diagonales[k] || {};
  }
  async function guardar(que) {
    DATOS.meta = DATOS.meta || {};
    DATOS.meta.nota = 'Diagonales como objeto propio (atraviesan las obras). Lo carga la autora desde la visualización (tarjeta y Expandir). Clave: los dos ids de ancla, ordenados, unidos por «~». conceptos: #dg-… → nombre y posteo de la diagonal.';
    const texto = JSON.stringify(DATOS, null, 1) + '\n';
    const P = window.P314B;
    try {
      if (P && P.modo === 'web') {
        if (!(await P.listo)) throw new Error('sin permiso de escritura');
        await P.escribirArchivo('diagonales.json', texto, 'diagonal: ' + que);
        return aviso('✓ guardado en el repo (' + que + ')');
      }
      if (P && P.modo === 'local') {
        const r = await fetch('/api/diagonales', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-P314B': '1' }, body: texto });
        if (r.ok) return aviso('✓ diagonales.json guardado (' + que + ')');
      }
    } catch (e) { aviso('No se pudo guardar: ' + e.message + '. Se descarga el archivo.'); }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([texto], { type: 'application/json' }));
    a.download = 'diagonales.json'; a.click();
    aviso('↓ diagonales.json descargado: reemplazá sitio/diagonales.json (abrí la obra con servidor.py para guardar directo).');
  }
  function aviso(txt) {
    let el = document.getElementById('dg-aviso');
    if (!el) { el = document.createElement('div'); el.id = 'dg-aviso'; document.body.appendChild(el); }
    el.textContent = txt; el.classList.add('open');
    clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('open'), 4200);
  }

  // ── lo que se muestra de una diagonal ──
  DG.nodos = (a, b, t) => { const r = reg(a, b); return r.nodos || (t && t.lemas) || []; };
  DG.concepto = (a, b) => reg(a, b).concepto || '';
  DG.posteo = (a, b) => { const c = DG.concepto(a, b); return c && DATOS.conceptos[c] ? DATOS.conceptos[c].posteo || '' : ''; };
  function instrumentoHtml(t) {
    if (!t.instrumento) return '';
    const label = LABELS[t.instrumento] || t.instrumento_nuevo_label || t.instrumento;
    return esc(label) + (t.instrumento_lema ? ' <small>› ' + esc(t.instrumento_lema) + '</small>' : '');
  }
  DG.destinoLabel = r => r.mismaObra ? (r.tituloCapitulo || r.tituloObra || 'en esta obra')
    : (r.tituloObra || '') + (r.tituloCapitulo ? ' · ' + r.tituloCapitulo : '');
  function datosHtml(t, nodos, concepto) {
    const f = [];
    if (t.tipo_relacion) f.push(['Relación', esc(t.tipo_relacion)]);
    if (t.signo) f.push(['Signo', esc(t.signo)]);
    if (t.instrumento) f.push(['Instrumento', instrumentoHtml(t)]);
    // Cluster: mientras la matriz no agrupe, son los nodos de la diagonal.
    // Cluster y concepto: la autora los ve (y edita) en su editor, más abajo;
    // acá van marcados para no mostrarlos dos veces.
    if (nodos.length) f.push(['Cluster', '<span class="diag-nodos">' + nodos.map(l => '<span>' + esc(l) + '</span>').join('') + '</span>', 1]);
    if (concepto) f.push(['Concepto', '<span class="dg-concepto">#' + esc(concepto) + '</span>', 1]);
    return f.map(x => '<div class="diag-dato' + (x[2] ? ' dg-lector' : '') + '"><span class="diag-k">' + x[0] + '</span><span class="diag-v">' + x[1] + '</span></div>').join('');
  }
  function temaHtml(t) {
    if (!t.titulo && !t.resumen) return '';
    return '<div class="dg-tema">' + (t.titulo ? '<div class="dg-tema-t">' + esc(t.titulo) + '</div>' : '')
      + (t.resumen ? '<div class="dg-tema-s">' + parrafos(t.resumen) + '</div>' : '') + '</div>';
  }
  function editorAutorHtml(a, b, nodos, concepto) {
    const nombre = concepto && DATOS.conceptos[concepto] ? DATOS.conceptos[concepto].nombre : '';
    return '<div class="dg-autor solo-autor" data-a="' + esc(a) + '" data-b="' + esc(b) + '">'
      + '<div class="dg-autor-fila"><span class="diag-k">Cluster</span><span class="dg-chips">'
      + nodos.map((n, i) => '<span class="dg-chip">' + esc(n) + '<button data-dg="nodo-quitar" data-i="' + i + '" title="quitar">×</button></span>').join('')
      + '<input data-dg-nodo placeholder="+ nodo (Enter)" spellcheck="false"></span></div>'
      + '<div class="dg-autor-fila"><span class="diag-k">Concepto</span><span class="dg-conc-in">#' + PREFIJO
      + '<input data-dg-concepto value="' + esc(nombre) + '" placeholder="nombre (Enter)" spellcheck="false"></span></div>'
      + '</div>';
  }
  DG.botonIrDiagonal = (a, b) => {
    const p = DG.posteo(a, b);
    return p ? '<span class="accion-goto dg-ir-diag" data-dg="ir-diagonal" data-posteo="' + esc(p) + '" data-desde="' + esc(DG.clave(a, b)) + '">Ir hacia la diagonal</span>' : '';
  };

  // Copiar un enlace (a una diagonal, a un pasaje citado) y avisarlo abajo.
  // Sin permiso para el portapapeles, se muestra el enlace para copiarlo a mano.
  window.p314bCopiar = function (url) {
    function avisar(txt) {
      const v = document.createElement('div');
      v.className = 'aviso-copiado'; v.setAttribute('role', 'status'); v.textContent = txt;
      document.body.appendChild(v); setTimeout(() => v.remove(), 2200);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(() => avisar('enlace copiado'), () => prompt('Copiá el enlace:', url));
    else prompt('Copiá el enlace:', url);
  };

  // Tarjeta del ala. r = t._resuelto.
  DG.tarjeta = function (accion, t, r) {
    r = r || {};
    const a = accion.id, b = t.destino || '';
    const nodos = DG.nodos(a, b, t), concepto = DG.concepto(a, b);
    let cab, pie = '';
    if (r._pendiente) cab = 'diagonal · destino pendiente';
    else if (r._roto || !b) cab = 'diagonal sin destino';
    else cab = '<span class="dg-hacia">hacia</span> ' + esc(DG.destinoLabel(r) + (r.pdf_pagina != null ? ' · pág. ' + r.pdf_pagina : ''));
    if (r._pendiente) pie = '<div class="accion-pending">El destino todavía no está publicado.</div>';
    else if (r._roto || !b) pie = '<div class="accion-pending">Esta diagonal no tiene un ID de destino resoluble.</div>';
    else pie = '<div class="diagonal-ira"><span class="expandir-btn" data-dg="expandir" data-a="' + esc(a) + '" data-b="' + esc(b) + '">Expandir</span>'
      + '<span class="accion-goto" data-dg="ir" data-id="' + esc(b) + '">Ir al destino</span>' + botonLeer(a, b)
      + '<span class="accion-goto dg-copiar" data-dg="copiar" data-id="' + esc(a) + '" title="Copiar un enlace que lleva a esta diagonal">Copiar enlace</span></div>' + cajaLeer(a, b);
    return '<div class="diagonal-card dg-card' + (t.vacia ? ' dg-vacia' : '') + '" data-accion="' + esc(a) + '">'
      + '<div class="diagonal-fuente">' + cab + '</div>'
      + (t.vacia ? '<div class="dg-vacia-rot">ancla de diagonal vacía</div>' : '')
      + datosHtml(t, nodos, concepto)
      + temaHtml(t)
      + (b ? editorAutorHtml(a, b, nodos, concepto) : '')
      + pie + '</div>';
  };

  // Una fuente con varios destinos: si la acción lleva «diagonales_juntas»,
  // una sola tarjeta con todas las citas de destino y un solo emergente (el
  // de la primera diagonal que tenga); si no, una tarjeta por destino.
  DG.tarjetas = function (accion) {
    const ds = (accion.tipos || []).filter(t => t.tipo === 'diagonal');
    if (accion.diagonales_juntas && ds.length > 1) return [DG.tarjetaGrupo(accion, ds)];
    return ds.map(t => DG.tarjeta(accion, t, t._resuelto));
  };
  DG.tarjetaGrupo = function (accion, ds) {
    const a = accion.id;
    const conTexto = ds.find(t => (t.emergente || '').trim() || t.titulo || t.resumen) || ds[0];
    const filas = ds.map(t => {
      const r = t._resuelto || {}, b = t.destino || '';
      if (r._pendiente) return '<li class="dg-dest"><span class="dg-hacia">hacia</span> <span class="accion-pending">un destino todavía no publicado</span></li>';
      if (r._roto || !b) return '<li class="dg-dest"><span class="accion-pending">destino sin ID resoluble</span></li>';
      return '<li class="dg-dest"><div><span class="dg-hacia">hacia</span> ' + esc(DG.destinoLabel(r) + (r.pdf_pagina != null ? ' · pág. ' + r.pdf_pagina : '')) + (t.signo ? ' <small>· ' + esc(t.signo) + '</small>' : '') + '</div>'
        + (r.fragmento ? '<div class="dg-dest-cita">«' + esc(r.fragmento) + '»</div>' : '')
        + '<div class="diagonal-ira"><span class="expandir-btn" data-dg="expandir" data-a="' + esc(a) + '" data-b="' + esc(b) + '">Expandir</span>'
        + '<span class="accion-goto" data-dg="ir" data-id="' + esc(b) + '">Ir</span></div></li>';
    }).join('');
    return '<div class="diagonal-card dg-card dg-grupo">'
      + '<div class="diagonal-fuente">' + ds.length + ' destinos</div>'
      + '<ol class="dg-destinos">' + filas + '</ol>'
      + datosHtml(Object.assign({}, conTexto, { signo: null }), [], '')
      + temaHtml(conTexto)
      + ((conTexto.emergente || '').trim() ? '<div class="diagonal-emergente">' + parrafos(conTexto.emergente) + '</div>' : '')
      + '<div class="diagonal-ira"><span class="accion-goto dg-copiar" data-dg="copiar" data-id="' + esc(a) + '" title="Copiar un enlace que lleva a estas diagonales">Copiar enlace</span></div>'
      + '</div>';
  };

  // ── leer completo: el comienzo del posteo de la diagonal y su grafo ──
  // Solo si el concepto tiene posteo publicado. Lo abierto sigue abierto
  // cuando el ala se vuelve a pintar; el contenido se lee una vez de la
  // página del posteo (sus citas son las de todas las diagonales del
  // concepto, así que el grafo está al día con cada publicación).
  const LEER = { abiertas: new Set(), html: {}, posteos: {} };
  function botonLeer(a, b) {
    if (!DG.posteo(a, b)) return '';
    const k = DG.clave(a, b), abierta = LEER.abiertas.has(k);
    return '<span class="accion-goto dg-leer-btn" data-dg="leer" data-a="' + esc(a) + '" data-b="' + esc(b) + '" aria-expanded="' + abierta + '">'
      + (abierta ? 'cerrar lectura' : 'leer completo') + '</span>';
  }
  function cajaLeer(a, b) {
    const k = DG.clave(a, b);
    if (!DG.posteo(a, b) || !LEER.abiertas.has(k)) return '';
    if (!LEER.html[k]) setTimeout(() => llenarLeer(a, b), 0);
    return '<div class="dg-leer" data-leer="' + esc(k) + '">' + (LEER.html[k] || '<div class="dgx-cargando">cargando…</div>') + '</div>';
  }
  function leerPosteo(slug) {
    LEER.posteos[slug] = LEER.posteos[slug] || fetch(new URL('obras/' + encodeURIComponent(slug) + '.html', BASE), { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }).then(html => {
        const ch = /const CHAPTERS = (\[[\s\S]*?\]);\n/.exec(html), dp = /const DIAGONAL_POSTEO = (.*);\n/.exec(html);
        const caps = ch ? JSON.parse(ch[1]) : [], datos = dp ? JSON.parse(dp[1]) : null;
        // DOMParser: el texto se lee sin cargar las imágenes del posteo.
        // El comienzo es el de los párrafos (sin títulos ni epígrafes pegados).
        const doc = new DOMParser().parseFromString((caps[0] || {}).body || '', 'text/html').body;
        const ps = [...doc.querySelectorAll('p')].map(p => p.textContent.replace(/\s+/g, ' ').trim()).filter(t => t.length > 40);
        const plano = (ps.length ? ps.join(' ') : doc.textContent).replace(/\s+/g, ' ').trim();
        let inicio = plano.slice(0, 320);
        if (plano.length > 320) { const p = inicio.lastIndexOf('. '); inicio = (p > 160 ? inicio.slice(0, p + 1) : inicio.replace(/\s+\S*$/, '')) + ' …'; }
        return { inicio, citas: (datos && datos.citas) || [], nombre: (datos && datos.nombre) || '' };
      });
    return LEER.posteos[slug];
  }
  // Las obras son islas; cada diagonal del concepto, una arista entre sus
  // dos citas. La diagonal desde la que se abre va resaltada.
  function grafoHtml(citas, k) {
    const islas = [], deIsla = {};
    const nodo = x => {
      const clave = x.archivo || x.obra || '?';
      if (!(clave in deIsla)) { deIsla[clave] = islas.length; islas.push({ t: x.obra || '', nodos: [] }); }
      const isla = islas[deIsla[clave]];
      let n = isla.nodos.find(m => m.id === x.id);
      if (!n) { n = { id: x.id, x, isla: deIsla[clave] }; isla.nodos.push(n); }
      return n;
    };
    const aristas = citas.filter(c => c.fuente && c.destino).map(c => ({ c, f: nodo(c.fuente), d: nodo(c.destino) }));
    if (!aristas.length) return '';
    const W = 300, H = islas.length > 2 ? 190 : 130, cx = W / 2, cy = H / 2;
    const R = islas.length === 1 ? 0 : Math.min(W, H * 1.6) / 2 - 42;
    islas.forEach((is, i) => {
      const ang = islas.length === 2 ? (i ? 0 : Math.PI) : -Math.PI / 2 + i * 2 * Math.PI / islas.length;
      is.x = cx + R * Math.cos(ang); is.y = cy + (islas.length === 2 ? 0 : R * 0.62 * Math.sin(ang));
      is.r = Math.min(34, 14 + is.nodos.length * 5);
      is.nodos.forEach((n, j) => {
        const a2 = j * 2 * Math.PI / is.nodos.length, rr = is.nodos.length > 1 ? is.r * 0.55 : 0;
        n.px = is.x + rr * Math.cos(a2); n.py = is.y + rr * Math.sin(a2);
      });
    });
    const esta = new Set(); aristas.forEach(e => { if (e.c.clave === k) { esta.add(e.f.id); esta.add(e.d.id); } });
    const corto = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
    let svg = '<svg class="dg-grafo" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Diagonales del concepto entre ' + islas.length + ' obra' + (islas.length > 1 ? 's' : '') + '">';
    islas.forEach(is => {
      svg += '<circle class="isla" cx="' + is.x.toFixed(1) + '" cy="' + is.y.toFixed(1) + '" r="' + is.r + '"/>'
        + '<text class="isla-t" x="' + is.x.toFixed(1) + '" y="' + Math.min(H - 3, is.y + is.r + 10).toFixed(1) + '" text-anchor="middle">' + esc(corto(is.t, 26)) + '</text>';
    });
    aristas.forEach(e => {
      const mx = (e.f.px + e.d.px) / 2, my = (e.f.py + e.d.py) / 2 - (e.f.isla === e.d.isla ? 14 : 18);
      svg += '<path class="arista' + (e.c.clave === k ? ' esta' : '') + '" d="M' + e.f.px.toFixed(1) + ' ' + e.f.py.toFixed(1) + ' Q' + mx.toFixed(1) + ' ' + my.toFixed(1) + ' ' + e.d.px.toFixed(1) + ' ' + e.d.py.toFixed(1) + '"><title>' + esc(e.c.titulo || e.c.relacion || 'diagonal') + '</title></path>';
    });
    islas.forEach(is => is.nodos.forEach(n => {
      const aqui = !!acciones()[n.id];
      svg += '<circle class="nodo' + (esta.has(n.id) ? ' esta' : '') + (aqui ? ' ir' : '') + '"' + (aqui ? ' data-dg="ir" data-id="' + esc(n.id) + '"' : '')
        + ' cx="' + n.px.toFixed(1) + '" cy="' + n.py.toFixed(1) + '" r="' + (esta.has(n.id) ? 5 : 4) + '"><title>' + esc([n.x.obra, n.x.capitulo].filter(Boolean).join(' · ') + ' — «' + corto(n.x.frag, 90) + '»') + '</title></circle>';
    }));
    return svg + '</svg><div class="dg-leer-pie">' + aristas.length + ' diagonal' + (aristas.length > 1 ? 'es' : '') + ' · ' + islas.length + ' obra' + (islas.length > 1 ? 's' : '') + '</div>';
  }
  async function llenarLeer(a, b) {
    const k = DG.clave(a, b), slug = DG.posteo(a, b);
    let html;
    try {
      const p = await leerPosteo(slug);
      html = '<div class="dg-leer-n">#' + esc(DG.concepto(a, b)) + (p.nombre ? ' · ' + esc(p.nombre) : '') + '</div>'
        + (p.inicio ? '<p class="dg-leer-t">' + esc(p.inicio) + '</p>' : '')
        + grafoHtml(p.citas, k)
        + '<div class="diagonal-ira">' + DG.botonIrDiagonal(a, b).replace('dg-ir-diag', 'dg-ir-diag dg-ir-leer') + '</div>';
    } catch (e) {
      delete LEER.posteos[slug];
      html = '<div class="dgx-vacio">No se pudo leer el posteo de la diagonal (' + esc(e.message || e) + ').</div>';
    }
    LEER.html[k] = html;
    document.querySelectorAll('.dg-leer').forEach(el => { if (el.dataset.leer === k) el.innerHTML = html; });
  }
  // Se abre en el lugar: la tarjeta puede estar en un ala o en la ventana
  // de lectura del celular, que no se vuelve a pintar.
  function alternarLeer(a, b) {
    const k = DG.clave(a, b), abrir = !LEER.abiertas.has(k);
    if (abrir) LEER.abiertas.add(k); else LEER.abiertas.delete(k);
    document.querySelectorAll('.dg-card [data-dg="leer"]').forEach(btn => {
      if (DG.clave(btn.dataset.a, btn.dataset.b) !== k) return;
      btn.textContent = abrir ? 'cerrar lectura' : 'leer completo';
      btn.setAttribute('aria-expanded', String(abrir));
      const pie = btn.closest('.diagonal-ira'), caja = pie && pie.nextElementSibling;
      if (caja && caja.classList.contains('dg-leer')) caja.remove();
      if (abrir && pie) pie.insertAdjacentHTML('afterend', cajaLeer(a, b));
    });
  }

  // ── edición desde la tarjeta (solo la autora) ──
  function tipoDiagonal(a, b) {
    const acc = acciones()[a];
    return acc ? (acc.tipos || []).find(x => x.tipo === 'diagonal' && x.destino === b) : null;
  }
  function refrescar() { if (typeof DG.alCambiar === 'function') DG.alCambiar(); }
  function agregarNodo(a, b, v) {
    v = v.trim().toLowerCase(); if (!v) return;
    const r = reg(a, b, true), actuales = DG.nodos(a, b, tipoDiagonal(a, b));
    if (actuales.includes(v)) return;
    r.nodos = actuales.concat(v);
    guardar('nodo «' + v + '»'); refrescar();
  }
  function quitarNodo(a, b, i) {
    const r = reg(a, b, true), actuales = DG.nodos(a, b, tipoDiagonal(a, b)).slice();
    const [fuera] = actuales.splice(i, 1);
    r.nodos = actuales;
    guardar('quitar nodo «' + fuera + '»'); refrescar();
  }
  function ponerConcepto(a, b, nombre) {
    nombre = nombre.trim();
    const r = reg(a, b, true);
    if (!nombre) { delete r.concepto; guardar('sin concepto'); refrescar(); return; }
    const id = PREFIJO + DG.slug(nombre);
    r.concepto = id;
    DATOS.conceptos[id] = DATOS.conceptos[id] || { nombre: nombre, posteo: null };
    guardar('concepto #' + id); refrescar();
  }
  // Las tarjetas viven en alas que se cierran con cualquier clic en la
  // página: lo que pasa dentro de una tarjeta se atiende acá y no sigue.
  document.addEventListener('click', e => {
    const card = e.target.closest('.dg-card');
    if (!card) return;
    e.stopPropagation();
    const btn = e.target.closest('[data-dg]');
    if (!btn) return;
    const ed = btn.closest('.dg-autor');
    const acc = btn.dataset.dg;
    if (acc === 'expandir') DG.expandir(btn.dataset.a, btn.dataset.b);
    else if (acc === 'ir' && typeof irAAccion === 'function') irAAccion(btn.dataset.id);
    else if (acc === 'ir-diagonal') irHaciaDiagonal(btn.dataset.posteo, btn.dataset.desde);
    else if (acc === 'leer') alternarLeer(btn.dataset.a, btn.dataset.b);
    else if (acc === 'copiar') window.p314bCopiar(location.origin + location.pathname + '#accion=' + encodeURIComponent(btn.dataset.id));
    else if (acc === 'nodo-quitar' && ed) quitarNodo(ed.dataset.a, ed.dataset.b, +btn.dataset.i);
  }, true);
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const ed = e.target.closest && e.target.closest('.dg-autor');
    if (!ed) return;
    e.preventDefault();
    if (e.target.hasAttribute('data-dg-nodo')) agregarNodo(ed.dataset.a, ed.dataset.b, e.target.value);
    if (e.target.hasAttribute('data-dg-concepto')) ponerConcepto(ed.dataset.a, ed.dataset.b, e.target.value);
  });
  function irHaciaDiagonal(posteo, desde) {
    if (!posteo) return;
    location.href = new URL('obras/' + encodeURIComponent(posteo) + '.html' + (desde ? '?desde=' + encodeURIComponent(desde) : ''), BASE).href;
  }

  // ── lemas en común (reglas generales + lemas.json) ──
  const VACIAS = new Set(('que como para pero porque sino aunque cuando donde entre sobre desde hasta este esta esto estos estas ese esa eso esos esas aquel aquella sólo solo tanto tan más menos muy también ella ellos ellas nuestro nuestra nuestros nuestras decir dicho hacer sido será sean siendo cual cuales quien quienes todo toda todos todas otro otra otros otras nada algo cada mismo misma ante bajo tras '
    + 'el la lo los las un una unos unas de del al en y e o u a con por sin se su sus le les me te nos os mi tu es son fue era ser hay ha han he no ni si ya así asi aquí acá ahí allí cuyo cuya').split(' ').map(w => w.normalize('NFD').replace(/[\u0300-\u036f]/g, '')));
  const IRREG = {
    es: 'ser', son: 'ser', era: 'ser', eran: 'ser', fue: 'ser', fueron: 'ser', sea: 'ser', sean: 'ser', siendo: 'ser', sido: 'ser', sera: 'ser', soy: 'ser', somos: 'ser', seria: 'ser',
    esta: 'estar', estan: 'estar', estaba: 'estar', estando: 'estar', estamos: 'estar',
    tiene: 'tener', tienen: 'tener', tenia: 'tener', tenga: 'tener', tuvo: 'tener',
    hace: 'hacer', hacen: 'hacer', hizo: 'hacer', hecho: 'hacer', haciendo: 'hacer',
    dice: 'decir', dicen: 'decir', dijo: 'decir', diciendo: 'decir', decimos: 'decir', diriamos: 'decir', deciamos: 'decir',
    puede: 'poder', pueden: 'poder', podia: 'poder', pudo: 'poder', podemos: 'poder', podria: 'poder', podriamos: 'poder',
  };
  let LEM = null;
  // lemas.json (lo que decidió la autora) + lemas-auto.json (el diccionario,
  // lo arma lemas_auto.py). Sin lemas-auto.json, solo reglas, como antes.
  const leerJson = ruta => fetch(BASE + ruta, { cache: 'no-store' }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  function lemasArchivo() {
    if (LEM) return LEM;
    const propio = typeof LEMAS !== 'undefined' && LEMAS ? Promise.resolve(LEMAS) : leerJson('lemas.json');
    return (LEM = Promise.all([propio, leerJson('lemas-auto.json')]).then(([L, A]) => {
      const auto = {};
      (A.propias || []).forEach(w => { auto[w] = w; });
      Object.assign(auto, A.formas || {});
      return Object.assign({}, L, { auto, _lemasAuto: new Set(Object.values(auto).map(norm)) });
    }));
  }
  const norm = w => w.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  function lema(w, L) {
    const bajo = w.toLowerCase();
    if (bajo === 'sí') return 'sí';
    const F = L.formas || {};
    // solo claves propias: «constructor» o «tostring» en un texto no son lemas
    const propia = (o, k) => Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined;
    const dado = propia(F, bajo) || propia(F, norm(bajo));
    if (dado) return dado === 'sí' ? 'sí' : norm(dado);
    let n = norm(w);
    if (propia(IRREG, n)) return IRREG[n];
    // el diccionario (lemas-auto.json); si su lema está en lemas.json, manda ese
    const auto = L.auto && Object.prototype.hasOwnProperty.call(L.auto, bajo) ? L.auto[bajo] : null;
    if (auto) return norm(propia(F, auto) || propia(F, norm(auto)) || auto);
    if (n.length > 7) n = n.replace(/mente$/, '');
    // plurales y verbos regulares (formas → infinitivo aproximado), para lo
    // que el diccionario no conoce
    const reglas = [[/ciones$/, 'cion'], [/siones$/, 'sion'], [/idades$/, 'idad'], [/ces$/, 'z'],
      [/iendo$/, 'er'], [/ando$/, 'ar'], [/(ados|adas|ado|ada)$/, 'ar'], [/(idos|idas|ido|ida)$/, 'er'],
      [/(abamos|aban|abas|aba)$/, 'ar'], [/(iamos|ian)$/, 'er'], [/(aron|amos)$/, 'ar'], [/(ieron|emos|imos)$/, 'er'],
      [/ones$/, 'on'], [/([^aeiou])es$/, '$1'], [/([aeiou])s$/, '$1']];
    for (const [rx, rep] of reglas) if (rx.test(n)) { n = n.replace(rx, rep); break; }
    return n;
  }
  // Clave de comparación: el lema sin la terminación del infinitivo, para
  // que un lema aproximado (ar/er/ir) no separe lo que es lo mismo
  // (distinguimos / distinguir). Femenino y masculino NO se juntan: la
  // autora lo revisó y casi siempre era otra palabra (diga/digo, casa/caso,
  // marca/marco). Lo que cargás en lemas.json manda: esa forma se compara
  // tal cual la escribiste.
  function clave(w, L) {
    const l = lema(w, L);
    const F = L.formas || {};
    if (!L._lemas) L._lemas = new Set(Object.values(F).map(x => x.toLowerCase()));
    const tiene = k => Object.prototype.hasOwnProperty.call(F, k);
    if (l === 'sí' || tiene(w.toLowerCase()) || tiene(norm(w))) return l;
    // una palabra que es lema en lemas.json se compara tal cual (indiferir)
    if (L._lemas.has(w.toLowerCase())) return w.toLowerCase();
    // lo que viene del diccionario (o cae en uno de sus lemas) va tal cual
    if ((L.auto && Object.prototype.hasOwnProperty.call(L.auto, w.toLowerCase())) || (L._lemasAuto && L._lemasAuto.has(l))) return l;
    const c = l.replace(/(ar|er|ir)$/, '');
    return c.length >= 4 ? c : l;
  }
  const TOKEN = /[\p{L}\-]{2,}/gu;
  function vacia(w, L) { return VACIAS.has(norm(w)) || (L.ignorar || []).some(x => norm(x) === norm(w)); }
  function cuenta(w, L) { return w.toLowerCase() === 'sí' || (w.length >= 3 && !vacia(w, L)); }
  function lemasDe(txt, L) { return new Set((String(txt).match(TOKEN) || []).filter(w => cuenta(w, L)).map(w => clave(w, L))); }
  function marcarComunes(el, comunes, L) {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodos = []; let n;
    while ((n = w.nextNode())) if (!n.parentNode.closest('.dg-comun, button, .solo-autor, .dgx-orden')) nodos.push(n);
    nodos.forEach(n => {
      const partes = n.nodeValue.split(/([\p{L}\-]{2,})/u);
      if (partes.length < 2) return;
      const f = document.createDocumentFragment();
      partes.forEach(p => {
        if (/^[\p{L}\-]{2,}$/u.test(p) && cuenta(p, L) && comunes.has(clave(p, L))) {
          const s = document.createElement('span'); s.className = 'dg-comun'; s.textContent = p; f.appendChild(s);
        } else f.appendChild(document.createTextNode(p));
      });
      n.replaceWith(f);
    });
  }
  function desmarcar(el, clase) {
    el.querySelectorAll('span.' + clase).forEach(s => s.replaceWith(document.createTextNode(s.textContent)));
    el.normalize();
  }

  // ── contexto de una cita: la oración, una antes y una después ──
  const LIMITE = 300, MARGEN = 90;
  function oraciones(txt) {
    const out = []; const RX = /[.!?…]+["'»”’)\]]*\s+(?=[¿¡«"“(\[A-ZÁÉÍÓÚÜÑ0-9'\-])/g; let ini = 0, m;
    while ((m = RX.exec(txt))) { const fin = m.index + m[0].length; out.push([ini, fin]); ini = fin; }
    if (ini < txt.length) out.push([ini, txt.length]);
    return out;
  }
  const plano = s => String(s || '').replace(/\s+/g, ' ').trim();
  // Párrafo de una cita que vive en OTRA obra de texto (lo usan los
  // posteos-PDF, que no tienen el cargador de obra-template.html). Lee los
  // datos embebidos en la página publicada de esa obra. Si el destino es otro
  // PDF, no hay texto que leer sin abrirlo: devuelve '' y queda la cita.
  const OBRAS = {};
  DG.parrafoEnObra = function (archivo, id, frag) {
    if (!archivo) return Promise.resolve('');
    OBRAS[archivo] = OBRAS[archivo] || fetch(new URL(archivo, location.href)).then(r => r.ok ? r.text() : '').then(html => {
      const ch = /const CHAPTERS = (\[[\s\S]*?\]);\n/.exec(html), ac = /const ACCIONES = (\{[\s\S]*?\});\n/.exec(html);
      return ch && ac ? { chapters: JSON.parse(ch[1]), acciones: JSON.parse(ac[1]) } : null;
    }).catch(() => null);
    return OBRAS[archivo].then(d => {
      if (!d) return '';
      const acc = d.acciones[id] || {}, cap = d.chapters.find(c => c.id === acc.capitulo);
      if (!cap) return '';
      const cont = new DOMParser().parseFromString(String(cap.body || '').includes('<') ? cap.body : String(cap.body || '').split(/\n{2,}/).map(p => '<p>' + esc(p) + '</p>').join(''), 'text/html').body;
      const plano = el => el.textContent.replace(/\s+/g, ' ').trim();
      let bloques = [...cont.children];
      if (bloques.length === 1 && bloques[0].children.length > 1) bloques = [...bloques[0].children];
      const f = String(frag || acc.fragmento || '').replace(/\s+/g, ' ').trim();
      const conMarca = bloques.filter(b => [...b.querySelectorAll('.accion-mark')].concat(b.matches('.accion-mark') ? [b] : [])
        .some(m => (m.dataset.accion || '').split(',').includes(id)));
      const hallados = conMarca.length ? conMarca : bloques.filter(b => f && plano(b).includes(f.slice(0, 80)));
      return hallados.map(plano).join(' ');
    });
  };

  DG.contexto = function (parrafo, frag) {
    const texto = plano(parrafo), f = plano(frag);
    const i = f ? texto.indexOf(f) : -1;
    if (i < 0) return { texto: f || texto.slice(0, LIMITE), ini: f ? 0 : -1, largo: f.length };
    const ors = oraciones(texto);
    let a = ors.findIndex(([x, y]) => y > i), b = ors.findIndex(([x, y]) => y >= i + f.length);
    if (a < 0) a = 0; if (b < 0) b = ors.length - 1;
    const largo = () => ors[b][1] - ors[a][0];
    // una antes y una después, dentro del párrafo, si entran en ~300
    // caracteres (con margen para no cortar una oración)
    if (a > 0 && largo() + (ors[a - 1][1] - ors[a - 1][0]) <= LIMITE + MARGEN) a--;
    if (b < ors.length - 1 && largo() + (ors[b + 1][1] - ors[b + 1][0]) <= LIMITE + MARGEN) b++;
    const ini = ors[a][0];
    return { texto: texto.slice(ini, ors[b][1]).trim(), ini: i - ini, largo: f.length, completo: texto };
  };

  // Envuelve la primera aparición de un texto (aunque cruce nodos).
  function envolver(cont, str, clase, datos) {
    const objetivo = plano(str);
    if (!objetivo) return [];
    const w = document.createTreeWalker(cont, NodeFilter.SHOW_TEXT), nodos = []; let pl = '', n;
    while ((n = w.nextNode())) { nodos.push({ n, ini: pl.length }); pl += n.nodeValue.replace(/\s/g, ' '); }
    const rx = new RegExp(objetivo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+'));
    const m = rx.exec(pl); if (!m) return [];
    const a = m.index, b = a + m[0].length, spans = [];
    nodos.slice().reverse().forEach(({ n, ini }) => {
      const fin = ini + n.nodeValue.length;
      if (fin <= a || ini >= b) return;
      const r = document.createRange(); r.setStart(n, Math.max(a, ini) - ini); r.setEnd(n, Math.min(b, fin) - ini);
      const sp = document.createElement('span'); sp.className = clase;
      Object.keys(datos || {}).forEach(k => { sp.dataset[k] = datos[k]; });
      r.surroundContents(sp); spans.unshift(sp);
    });
    return spans;
  }

  // ── Expandir ──
  const X = { a: '', b: '', t: null, lados: {}, vinculando: null, comunes: false };
  function montar() {
    if (document.getElementById('dgx')) return;
    const el = document.createElement('div');
    el.className = 'dgx'; el.id = 'dgx';
    el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-label', 'Expandir la diagonal');
    el.innerHTML = `<div class="dgx-ventana">
      <div class="dgx-cab"><span id="dgx-tit"></span>
        <span class="dgx-cab-der"><label class="dgx-tg"><input type="checkbox" id="dgx-comunes"> lemas en común</label>
        <button class="dgx-cerrar" data-x="cerrar">cerrar ×</button></span></div>
      <div class="dgx-cuerpo">
        <section class="dgx-lado" data-lado="o"><div class="dgx-r">origen</div><div class="dgx-et" id="dgx-o-et"></div><span class="dgx-orden" id="dgx-o-or" hidden></span>
          <div class="dgx-p" id="dgx-o"></div><button class="accion-goto" data-x="ir-o">Ir a la fuente</button></section>
        <section class="dgx-centro"><div class="dgx-r dgx-r-diag">diagonal</div><div id="dgx-datos"></div><h3 class="dgx-titulo" id="dgx-titulo" hidden></h3>
          <div class="dgx-em" id="dgx-em"></div><div class="dgx-glosa" id="dgx-glosa"></div>
          <div class="dgx-notas" id="dgx-notas"></div><div id="dgx-ir-diag"></div></section>
        <section class="dgx-lado" data-lado="d"><div class="dgx-r">destino</div><div class="dgx-et" id="dgx-d-et"></div><span class="dgx-orden" id="dgx-d-or" hidden></span>
          <div class="dgx-p" id="dgx-d"></div><button class="accion-goto" data-x="ir-d">Ir al destino</button></section>
      </div>
      <div class="dgx-pie" id="dgx-pie"></div>
      <div class="dgx-herr solo-autor" id="dgx-herr" hidden><button data-x="vincular">vincular a un pasaje</button><button data-x="anclar">ancla de diagonal</button></div>
    </div>`;
    document.body.appendChild(el);
    // que tocar vincular / anclar no borre la selección del emergente
    el.querySelector('#dgx-herr').addEventListener('mousedown', e => e.preventDefault());
    el.addEventListener('click', e => {
      e.stopPropagation();
      if (e.target === el) return cerrar();
      const b = e.target.closest('[data-x]');
      if (b) accionX(b.dataset.x, b);
      const v = e.target.closest('.dg-vin');
      if (v) mostrarVinculo(v.dataset.vin);
      const an = e.target.closest('.dg-anc');
      if (an) mostrarAncla(an.dataset.anc);
    });
    el.querySelector('#dgx-comunes').addEventListener('change', e => { X.comunes = e.target.checked; pintarComunes(); });
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape' || !el.classList.contains('open')) return;
      if (X.vinculando) { X.vinculando = null; pie(''); return; }
      cerrar();
    });
    document.addEventListener('mouseup', () => setTimeout(alSeleccionar, 0));
  }
  function cerrar() { document.getElementById('dgx').classList.remove('open'); X.vinculando = null; herramientas(null); }
  const pie = txt => { document.getElementById('dgx-pie').textContent = txt; };

  DG.expandir = async function (a, b) {
    await DG.cargar();
    montar();
    const t = tipoDiagonal(a, b); if (!t) return;
    Object.assign(X, { a, b, t, lados: {}, vinculando: null });
    if (typeof clearPin === 'function') clearPin();
    const acc = acciones()[a] || {};
    document.getElementById('dgx-tit').textContent = 'expandir · «' + plano(acc.fragmento).slice(0, 60) + (plano(acc.fragmento).length > 60 ? '…' : '') + '»';
    const nodos = DG.nodos(a, b, t), concepto = DG.concepto(a, b);
    document.getElementById('dgx-datos').innerHTML = datosHtml(t, nodos, concepto);
    const tit = document.getElementById('dgx-titulo'); tit.textContent = t.titulo || ''; tit.hidden = !t.titulo;
    document.getElementById('dgx-ir-diag').innerHTML = DG.posteo(a, b) ? '<button class="accion-goto" data-x="ir-diagonal">Ir hacia la diagonal</button>' : '';
    ['o', 'd'].forEach(l => { document.getElementById('dgx-' + l).innerHTML = '<i class="dgx-cargando">cargando…</i>'; document.getElementById('dgx-' + l + '-or').hidden = true; });
    document.getElementById('dgx-glosa').className = 'dgx-glosa';
    pintarCentro();
    pie('');
    document.getElementById('dgx').classList.add('open');
    let par;
    try { par = await window.DIAG_HOST.par(a, b); }
    catch (e) { par = { o: { frag: acc.fragmento, etiqueta: '' }, d: { frag: (t._resuelto || {}).fragmento, etiqueta: '', error: e.message } }; }
    [['o', a, par.o], ['d', b, par.d]].forEach(([l, id, s]) => {
      s = s || {};
      X.lados[l] = { id, s, ctx: DG.contexto(s.parrafo || s.frag || '', s.frag || ''), entero: false };
      document.getElementById('dgx-' + l + '-et').textContent = s.etiqueta || '';
      const or = document.getElementById('dgx-' + l + '-or'); or.textContent = s.orden || ''; or.hidden = !s.orden;
      pintarLado(l);
    });
    pintarComunes();
  };
  function pintarLado(l) {
    const S = X.lados[l], el = document.getElementById('dgx-' + l);
    const txt = S.entero && S.ctx.completo ? S.ctx.completo : S.ctx.texto;
    el.textContent = txt;
    if (S.s.frag) envolver(el, S.s.frag, 'dg-cita');
    if (!S.entero && S.ctx.completo && S.ctx.completo.length > S.ctx.texto.length) el.insertAdjacentHTML('beforeend', ' <button class="dgx-mas" data-x="mas-' + l + '">párrafo entero</button>');
    if (S.s.error) el.insertAdjacentHTML('beforeend', '<div class="dgx-cargando">(' + esc(S.s.error) + ')</div>');
  }
  function vinculos() {
    const t = X.t || {}, r = reg(X.a, X.b);
    // las referencias cargadas en el taller son vínculos del mismo tipo
    const delTaller = [];
    (t.referencias || []).forEach((rf, i) => {
      if (!rf || !rf.expr) return;
      if (rf.fuente) delTaller.push({ id: 'tf' + i, expr: rf.expr, accion: X.a, texto: rf.fuente, taller: true });
      if (rf.remitente) delTaller.push({ id: 'tr' + i, expr: rf.expr, accion: X.b, texto: rf.remitente, taller: true });
    });
    return delTaller.concat(r.vinculos || []);
  }
  function pintarCentro() {
    const t = X.t || {}, r = reg(X.a, X.b), em = document.getElementById('dgx-em');
    em.innerHTML = t.emergente ? parrafos(t.emergente) : '<p class="dgx-vacio">Sin emergente.</p>';
    vinculos().forEach(v => envolver(em, v.expr, 'dg-vin', { vin: v.id }));
    (r.anclas || []).forEach(an => envolver(em, an.expr, 'dg-anc', { anc: an.id }));
    const notas = r.notas || [];
    document.getElementById('dgx-notas').innerHTML = (notas.length ? '<div class="dgx-r">notas</div>' : '')
      + notas.map(n => '<div class="dgx-nota">' + parrafos(n.texto) + '<span class="dgx-nota-f">' + esc(n.fecha || '')
        + '</span><button class="solo-autor dgx-x" data-x="nota-quitar" data-id="' + esc(n.id) + '" title="quitar">×</button></div>').join('')
      + '<div class="solo-autor dgx-nota-nueva"><textarea id="dgx-nota-t" placeholder="nota (queda debajo del emergente)" spellcheck="false"></textarea><button data-x="nota">+ nota</button></div>';
    if (X.comunes) pintarComunes();
  }
  async function pintarComunes() {
    const cont = ['dgx-o', 'dgx-em', 'dgx-d'].map(id => document.getElementById(id));
    cont.forEach(c => desmarcar(c, 'dg-comun'));
    if (!X.comunes) return pie('');
    const L = await lemasArchivo();
    // Solo el texto: los botones («párrafo entero») están en los dos lados
    // y salían siempre como coincidencia.
    const soloTexto = c => { const k = c.cloneNode(true); k.querySelectorAll('button, .solo-autor, .dgx-orden').forEach(x => x.remove()); return k.textContent; };
    const [A, E, B] = cont.map(c => lemasDe(soloTexto(c), L));
    const comunes = new Set([...A].filter(x => B.has(x) || E.has(x)).concat([...B].filter(x => E.has(x))));
    cont.forEach(c => marcarComunes(c, comunes, L));
    pie(comunes.size + ' lemas en común entre origen, diagonal y destino (reglas generales + lemas.json).');
  }
  function limpiarResaltes() {
    document.querySelectorAll('#dgx .dg-refto').forEach(s => s.replaceWith(document.createTextNode(s.textContent)));
    ['dgx-o', 'dgx-d'].forEach(id => document.getElementById(id).normalize());
    document.querySelectorAll('#dgx .dg-vin.activa, #dgx .dg-anc.activa').forEach(e => e.classList.remove('activa'));
  }
  function mostrarVinculo(id) {
    const v = vinculos().find(x => x.id === id); if (!v) return;
    limpiarResaltes();
    document.querySelectorAll('#dgx .dg-vin[data-vin="' + id + '"]').forEach(e => e.classList.add('activa'));
    const l = v.accion === X.a ? 'o' : v.accion === X.b ? 'd' : '';
    const gl = document.getElementById('dgx-glosa');
    let h = '<b>«' + esc(v.expr) + '»</b> → ' + (l === 'o' ? 'origen' : l === 'd' ? 'destino' : 'otro texto') + ': «' + esc(v.texto) + '»';
    if (l) {
      let sp = envolver(document.getElementById('dgx-' + l), v.texto, 'dg-refto');
      if (!sp.length && !X.lados[l].entero) { X.lados[l].entero = true; pintarLado(l); sp = envolver(document.getElementById('dgx-' + l), v.texto, 'dg-refto'); }
      if (!sp.length) h += ' <i>(no aparece en este texto)</i>';
    }
    if (autor() && !v.taller) h += ' <button class="solo-autor dgx-x" data-x="vin-quitar" data-id="' + esc(id) + '">quitar vínculo</button>';
    gl.innerHTML = h; gl.className = 'dgx-glosa open';
  }
  function mostrarAncla(id) {
    const an = (reg(X.a, X.b).anclas || []).find(x => x.id === id); if (!an) return;
    limpiarResaltes();
    document.querySelectorAll('#dgx .dg-anc[data-anc="' + id + '"]').forEach(e => e.classList.add('activa'));
    const gl = document.getElementById('dgx-glosa');
    gl.innerHTML = '<b>«' + esc(an.expr) + '»</b> ↗ diagonal hacia «' + esc(an.frag || an.destino) + '»' + (an.obra ? ' · ' + esc(an.obra) : '')
      + ' <button class="accion-goto" data-x="ir-ancla" data-id="' + esc(an.id) + '">Ir a</button>'
      + (autor() ? ' <button class="solo-autor dgx-x" data-x="anc-quitar" data-id="' + esc(an.id) + '">quitar</button>' : '');
    gl.className = 'dgx-glosa open';
  }

  // Selección de la autora: en el centro ofrece vincular / anclar; si está
  // vinculando, la selección en un lado completa el vínculo.
  let seleccion = null;
  function alSeleccionar() {
    const dgx = document.getElementById('dgx');
    if (!dgx || !dgx.classList.contains('open') || !autor()) return;
    const sel = window.getSelection(), txt = plano(sel && sel.toString());
    if (!txt) { if (!X.vinculando) herramientas(null); return; }
    const nodo = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentNode);
    if (X.vinculando) {
      const lado = nodo && nodo.closest('#dgx-o, #dgx-d');
      if (!lado) return;
      const l = lado.id === 'dgx-o' ? 'o' : 'd';
      const r = reg(X.a, X.b, true);
      r.vinculos = (r.vinculos || []).concat({ id: nuevoId('v-'), expr: X.vinculando, accion: X.lados[l].id, texto: txt });
      X.vinculando = null; sel.removeAllRanges(); pie('');
      guardar('vínculo «' + txt.slice(0, 30) + '»'); pintarCentro();
      return;
    }
    if (!nodo || !nodo.closest('#dgx-em')) { herramientas(null); return; }
    seleccion = txt;
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    herramientas(rect);
  }
  function herramientas(rect) {
    const h = document.getElementById('dgx-herr'); if (!h) return;
    if (!rect) { h.hidden = true; return; }
    h.hidden = false;
    h.style.left = Math.max(8, rect.left) + 'px';
    h.style.top = Math.max(8, rect.top - 36) + 'px';
  }
  async function accionX(que, btn) {
    const r = () => reg(X.a, X.b, true);
    if (que === 'cerrar') return cerrar();
    if (que === 'ir-o' || que === 'ir-d') { const id = que === 'ir-o' ? X.a : X.b; cerrar(); if (typeof irAAccion === 'function') irAAccion(id); return; }
    if (que === 'ir-diagonal') return irHaciaDiagonal(DG.posteo(X.a, X.b), DG.clave(X.a, X.b));
    if (que === 'mas-o' || que === 'mas-d') { const l = que.slice(-1); X.lados[l].entero = true; pintarLado(l); return pintarComunes(); }
    if (que === 'vincular') {
      X.vinculando = seleccion; herramientas(null); window.getSelection().removeAllRanges();
      return pie('Seleccioná en el origen o el destino el pasaje al que remite «' + seleccion + '» (Esc cancela).');
    }
    if (que === 'anclar') { herramientas(null); return elegirDestinoAncla(seleccion); }
    if (que === 'nota') {
      const ta = document.getElementById('dgx-nota-t'), txt = ta.value.trim(); if (!txt) return;
      r().notas = (r().notas || []).concat({ id: nuevoId('n-'), texto: txt, fecha: new Date().toISOString().slice(0, 10) });
      guardar('nota'); return pintarCentro();
    }
    if (que === 'nota-quitar') { r().notas = (r().notas || []).filter(n => n.id !== btn.dataset.id); guardar('quitar nota'); return pintarCentro(); }
    if (que === 'vin-quitar') { r().vinculos = (r().vinculos || []).filter(n => n.id !== btn.dataset.id); guardar('quitar vínculo'); document.getElementById('dgx-glosa').className = 'dgx-glosa'; return pintarCentro(); }
    if (que === 'anc-quitar') { r().anclas = (r().anclas || []).filter(n => n.id !== btn.dataset.id); guardar('quitar ancla'); document.getElementById('dgx-glosa').className = 'dgx-glosa'; return pintarCentro(); }
    if (que === 'ir-ancla') {
      const an = (r().anclas || []).find(x => x.id === btn.dataset.id); if (!an) return;
      if (acciones()[an.destino]) { cerrar(); return irAAccion(an.destino); }
      const corpus = await fetch(BASE + 'corpus.json', { cache: 'no-store' }).then(x => x.json()).catch(() => ({}));
      const o = (corpus.obras || []).find(x => x.id === an.obra);
      if (o && o._file) location.href = new URL(o._file + '#accion=' + an.destino, BASE).href;
      else aviso('Esa obra todavía no está publicada.');
    }
  }

  // Ancla de diagonal: la expresión del emergente tiende una diagonal hacia
  // cualquier ancla del corpus (se elige de acciones.json).
  async function registroAcciones() {
    const P = window.P314B;
    if (P && P.modo === 'web' && P.leerArchivo) { try { return JSON.parse(await P.leerArchivo('acciones.json')); } catch (e) {} }
    return fetch(BASE + 'acciones.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  }
  async function elegirDestinoAncla(expr) {
    const reg0 = await registroAcciones(), lista = Object.entries(reg0.acciones || {})
      .map(([id, a]) => ({ id, obra: (a.origen || {}).obra || '', frag: plano((a.origen || {}).fragmento) }))
      .filter(x => x.frag && x.id !== X.a && x.id !== X.b);
    if (!lista.length) return aviso('No se pudo leer acciones.json (abrí la obra con servidor.py, o en la web con el token).');
    let caja = document.getElementById('dgx-elegir');
    if (!caja) { caja = document.createElement('div'); caja.id = 'dgx-elegir'; document.querySelector('#dgx .dgx-ventana').appendChild(caja); }
    caja.innerHTML = '<div class="dgx-r">ancla de diagonal · «' + esc(expr) + '» → elegí el destino</div>'
      + '<input id="dgx-buscar" placeholder="buscar por texto u obra" spellcheck="false"><div id="dgx-lista"></div>'
      + '<button class="dgx-x" data-cancelar>cancelar</button>';
    caja.hidden = false;
    const pintar = q => {
      q = norm(q || '');
      document.getElementById('dgx-lista').innerHTML = lista.filter(x => !q || norm(x.frag + ' ' + x.obra).includes(q)).slice(0, 60)
        .map(x => '<button data-id="' + esc(x.id) + '"><b>' + esc(x.obra) + '</b> «' + esc(x.frag.slice(0, 110)) + (x.frag.length > 110 ? '…' : '') + '»</button>').join('');
    };
    pintar('');
    const inp = document.getElementById('dgx-buscar'); inp.focus();
    inp.oninput = () => pintar(inp.value);
    caja.onclick = e => {
      e.stopPropagation();
      if (e.target.closest('[data-cancelar]')) { caja.hidden = true; return; }
      const b = e.target.closest('[data-id]'); if (!b) return;
      const x = lista.find(y => y.id === b.dataset.id);
      const r = reg(X.a, X.b, true);
      r.anclas = (r.anclas || []).concat({ id: nuevoId('a-'), expr, destino: x.id, obra: x.obra, frag: x.frag.slice(0, 200) });
      caja.hidden = true;
      guardar('ancla de diagonal «' + expr.slice(0, 30) + '»'); pintarCentro();
    };
  }

  // ── Posteo de la diagonal (el comparativo) ──
  // Un posteo común, escrito en el taller, marcado con un concepto #dg-….
  // Arriba: concepto, causa, instrumento, fuente → destino. Alas en reposo:
  // las citas de todas las diagonales del concepto (fuente a la izquierda,
  // destino a la derecha), primero la diagonal desde la que se llegó. Desde
  // el cuerpo, una expresión vinculada activa su cita en el ala.
  let POSTEO = null, vinculandoPosteo = null;
  const conceptoInfo = () => (POSTEO && DATOS.conceptos[POSTEO.concepto]) || {};
  function ladoTxt(x) { return x ? [x.obra, x.capitulo].filter(Boolean).join(' · ') + (x.pdf_pagina != null ? ' · pág. ' + x.pdf_pagina : '') : ''; }
  function instrumentoDe(c) {
    if (!c.instrumento) return '';
    return esc(LABELS[c.instrumento] || c.instrumento_label || c.instrumento) + (c.instrumento_lema ? ' <small>› ' + esc(c.instrumento_lema) + '</small>' : '');
  }
  function ordenPar(c) {
    const f = c.fuente, d = c.destino;
    if (!f || !d) return ['', ''];
    const kf = [f.fecha, f.cap_idx], kd = [d.fecha, d.cap_idx];
    if (kf[0] === kd[0] && kf[1] === kd[1]) return ['', ''];
    const antes = kf[0] < kd[0] || (kf[0] === kd[0] && kf[1] < kd[1]);
    return antes ? ['anterior', 'posterior'] : ['posterior', 'anterior'];
  }
  DG.montarPosteo = async function (datos) {
    POSTEO = datos;
    await DG.cargar();
    const desde = new URLSearchParams(location.search).get('desde') || '';
    const i = datos.citas.findIndex(c => c.clave === desde);
    if (i > 0) datos.citas.unshift(datos.citas.splice(i, 1)[0]);
    POSTEO.base = i >= 0 ? datos.citas[0] : null;
    const pagina = document.getElementById('book-page');
    const cab = document.createElement('div');
    cab.className = 'dgp-cab';
    const b = POSTEO.base || datos.citas[0] || {};
    const unicos = xs => [...new Set(xs.filter(Boolean))];
    const rel = unicos(datos.citas.map(c => c.relacion)), ins = unicos(datos.citas.map(instrumentoDe));
    cab.innerHTML = '<div class="dgp-id">#' + esc(datos.concepto) + '</div>'
      + '<div class="diag-dato"><span class="diag-k">Concepto causal</span><span class="diag-v">' + esc(rel.join(' · ') || datos.nombre) + '</span></div>'
      + (ins.length ? '<div class="diag-dato"><span class="diag-k">Instrumento</span><span class="diag-v">' + ins.join(' · ') + '</span></div>' : '')
      + (b.fuente || b.destino ? '<div class="diag-dato"><span class="diag-k">Fuente → destino</span><span class="diag-v">' + esc(ladoTxt(b.fuente) || '—') + ' → ' + esc(ladoTxt(b.destino) || '—') + '</span></div>' : '')
      + '<div class="dgp-n">' + datos.citas.length + ' diagonal' + (datos.citas.length === 1 ? '' : 'es') + ' bajo este concepto</div>';
    pagina.insertBefore(cab, pagina.firstChild);
    const cuerpo = document.getElementById('text-body');
    new MutationObserver(() => { clearTimeout(cuerpo._dgp); cuerpo._dgp = setTimeout(marcarVinculosPosteo, 80); }).observe(cuerpo, { childList: true });
    marcarVinculosPosteo();
    DG.alasPosteo();
  };
  function citaHtml(c, lado, base) {
    const x = c[lado]; if (!x) return '';
    const [of, od] = ordenPar(c);
    const orden = lado === 'fuente' ? of : od;
    return '<div class="dgp-cita' + (base ? ' base' : '') + '" data-cita="' + esc(x.id) + '">'
      + '<div class="dgp-frag">«' + esc(x.frag) + '»</div>'
      + '<div class="dgp-meta">' + esc(ladoTxt(x)) + (orden ? ' · <span class="dgp-orden">' + orden + '</span>' : '') + '</div>'
      + (base ? '' : '<div class="dgp-meta">' + [esc(c.relacion), instrumentoDe(c)].filter(Boolean).join(' · ') + '</div>')
      + (x.archivo ? '<span class="accion-goto" data-dgp="ir" data-archivo="' + esc(x.archivo) + '" data-id="' + esc(x.id) + '">' + (lado === 'fuente' ? 'Ir a la fuente' : 'Ir al destino') + '</span>' : '')
      + '</div>';
  }
  DG.alasPosteo = function () {
    // Las citas ocupan las dos alas: la leyenda se esconde, como con
    // cualquier ala abierta, para no taparlas.
    if (!POSTEO) return;
    document.body.classList.add('alas-activas');
    const wl = document.getElementById('wing-left'), wr = document.getElementById('wing-right');
    if (!wl || !wr || (typeof pinnedList !== 'undefined' && pinnedList.length)) return;
    [['fuente', wl], ['destino', wr]].forEach(([lado, w]) => {
      const base = POSTEO.base && POSTEO.base[lado] ? '<div class="dgp-r">desde esta diagonal</div>' + citaHtml(POSTEO.base, lado, true) : '';
      const resto = POSTEO.citas.filter(c => c !== POSTEO.base).map(c => citaHtml(c, lado, false)).join('');
      w.innerHTML = '<div class="dgp-r dgp-lado">' + lado + '</div>' + base + (resto ? '<div class="dgp-r">otras diagonales · #' + esc(POSTEO.concepto) + '</div>' + resto : '');
      w.className = 'wing-content apilado active dgp-alas';
      w.style.top = '';
    });
  };
  function marcarVinculosPosteo() {
    const cuerpo = document.getElementById('text-body');
    if (!cuerpo || !POSTEO) return;
    (conceptoInfo().vinculos || []).forEach(v => {
      if (!cuerpo.querySelector('.dg-vin[data-vin="' + v.id + '"]')) envolver(cuerpo, v.expr, 'dg-vin', { vin: v.id });
    });
  }
  function activarCita(id) {
    if (typeof clearPin === 'function') clearPin();
    DG.alasPosteo();
    document.querySelectorAll('.dgp-cita.activa').forEach(e => e.classList.remove('activa'));
    document.querySelectorAll('.dgp-cita[data-cita="' + id + '"]').forEach(e => { e.classList.add('activa'); e.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });
  }
  document.addEventListener('click', e => {
    if (!POSTEO) return;
    const v = e.target.closest('#text-body .dg-vin');
    if (v) {
      e.stopPropagation(); e.preventDefault();
      const vin = (conceptoInfo().vinculos || []).find(x => x.id === v.dataset.vin);
      document.querySelectorAll('#text-body .dg-vin.activa').forEach(x => x.classList.remove('activa'));
      v.classList.add('activa');
      if (vin) activarCita(vin.cita);
      return;
    }
    const cita = e.target.closest('.dgp-cita');
    if (!cita) return;
    e.stopPropagation();
    const ir = e.target.closest('[data-dgp="ir"]');
    if (ir) {
      if (acciones()[ir.dataset.id] && typeof irAAccion === 'function') return irAAccion(ir.dataset.id);
      location.href = new URL('obras/' + ir.dataset.archivo + '#accion=' + encodeURIComponent(ir.dataset.id), BASE).href;
      return;
    }
    if (vinculandoPosteo) {
      const info = DATOS.conceptos[POSTEO.concepto] = DATOS.conceptos[POSTEO.concepto] || { nombre: POSTEO.nombre, posteo: null };
      info.vinculos = (info.vinculos || []).concat({ id: nuevoId('v-'), expr: vinculandoPosteo, cita: cita.dataset.cita });
      aviso('vínculo: «' + vinculandoPosteo.slice(0, 40) + '» → cita');
      vinculandoPosteo = null;
      document.body.classList.remove('dgp-vinculando');
      guardar('vínculo del posteo #' + POSTEO.concepto);
      marcarVinculosPosteo();
    }
  }, true);
  // La autora selecciona una expresión del cuerpo → «vincular a una cita».
  document.addEventListener('mouseup', () => setTimeout(() => {
    if (!POSTEO || !autor()) return;
    let h = document.getElementById('dgp-herr');
    const sel = window.getSelection(), txt = plano(sel && sel.toString());
    const nodo = sel && sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentNode);
    if (!txt || !nodo || !nodo.closest('#text-body')) { if (h) h.hidden = true; return; }
    if (!h) {
      h = document.createElement('div'); h.id = 'dgp-herr'; h.className = 'dgx-herr';
      h.innerHTML = '<button>vincular a una cita</button>';
      h.addEventListener('mousedown', e => e.preventDefault());
      h.addEventListener('click', e => {
        e.stopPropagation(); h.hidden = true;
        vinculandoPosteo = h.dataset.expr;
        document.body.classList.add('dgp-vinculando');
        if (typeof clearPin === 'function') clearPin();
        DG.alasPosteo();
        aviso('Tocá en un ala la cita a la que remite «' + vinculandoPosteo.slice(0, 40) + '» (Esc cancela).');
      });
      document.body.appendChild(h);
    }
    h.dataset.expr = txt;
    const r = sel.getRangeAt(0).getBoundingClientRect();
    h.style.left = Math.max(8, r.left) + 'px'; h.style.top = Math.max(8, r.top - 36) + 'px';
    h.hidden = false;
  }, 0));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && vinculandoPosteo) { vinculandoPosteo = null; document.body.classList.remove('dgp-vinculando'); }
  });

  DG.cargar();
})();
