/* ─────────────────────────────────────────────────────────────────
   pdf-viewer-core.js — visor de PDF reusable, virtualizado y con zoom.

   Por qué existe: lector.html (y el mini-visor del detail panel de
   index.html) renderizaban TODAS las páginas del PDF de una sola vez,
   cada una con su canvas completo + su capa de texto. Con un PDF de
   cientos de páginas (Aire en la cuerda tiene 411) eso satura el DOM
   y el navegador — es lo que Pepi reportó como "rompe la
   visualización". Este módulo renderiza solo lo que está cerca del
   viewport (igual que hace el visor nativo de cualquier navegador) y
   libera lo que quedó lejos, para que el costo no escale con el total
   de páginas del documento sino con cuántas se ven a la vez.

   Uso:
     const visor = await PDFViewerCore.montar({
       contenedor: document.getElementById('viewer-wrap'),  // el div que hace scroll
       datos: arrayBuffer,           // o { url: '...' }
       escalaInicial: 1.2,
       onPaginaVisible: (n, total) => {...},
       onSeleccion: (texto, pagina) => {...},  // al soltar el mouse con selección de texto
       onPaginaLista: (n, capaTexto) => {...}, // cuando la página tiene su capa de texto (para marcar citas)
       onListo: (totalPaginas) => {...},
       desde: 284, hasta: 419        // opcional: solo ese rango de páginas
     });
     visor.irAPagina(5);
     visor.setZoom(1.4);
     visor.getZoom();
     visor.paginaActual;
     visor.totalPaginas;
     visor.desde; visor.hasta;     // el rango montado (sin rango: 1 y totalPaginas)
     visor.destruir();

   Con rango (una «parte» de un PDF largo, sin generar un archivo nuevo),
   solo existen las páginas desde..hasta. Los números de página de la API
   siguen siendo los del PDF entero (las acciones y citas se anclan así);
   la etiqueta de cada hoja cuenta desde 1.

   Requiere que pdfjsLib ya esté cargado (script de pdf.js) y su
   GlobalWorkerOptions.workerSrc configurado ANTES de llamar a montar().
   Este módulo no toca esa configuración — la deja a cargo de quien lo
   use, porque distintas páginas del sitio pueden cargar pdf.js con
   distinta versión/CDN.
   ───────────────────────────────────────────────────────────────── */
(function (global) {
  'use strict';

  const VENTANA_RENDER = 3;      // páginas a cada lado de la visible que se mantienen renderizadas
  const MARGEN_OBSERVER = '900px'; // precarga: cuánto antes de entrar al viewport empieza a renderizar

  async function montar(opts) {
    const {
      contenedor,
      datos,
      escalaInicial = 1.2,
      onPaginaVisible = () => {},
      onSeleccion = () => {},
      onPaginaLista = () => {},
      onListo = () => {},
      desde: desdePedido,
      hasta: hastaPedido,
      onError = (e) => { console.error('[pdf-viewer-core]', e); }
    } = opts;

    if (!contenedor) throw new Error('pdf-viewer-core: falta contenedor');
    if (!global.pdfjsLib) throw new Error('pdf-viewer-core: pdfjsLib no está cargado');

    contenedor.innerHTML = '';
    contenedor.classList.add('pvcore-wrap');

    let pdfDoc, totalPaginas = 0;
    let escala = escalaInicial;
    let desde = 1, hasta = 0;
    let paginaActual = 1;
    let destruido = false;

    // dims[i] = { width, height } a escala 1 — se calcula una sola vez
    // por documento, independiente del zoom (el zoom solo multiplica).
    const dims = [];
    // Las tablas van indexadas desde 0 por posición en el rango.
    const ix = i => i - desde;
    const enRango = n => Math.max(desde, Math.min(hasta, n));
    const placeholders = []; // divs .pvcore-page, uno por página
    const renderState = [];  // 'vacio' | 'renderizando' | 'listo', uno por página
    let observer = null;

    try {
      const loadingTask = datos && datos.url
        ? global.pdfjsLib.getDocument(datos.url)
        : global.pdfjsLib.getDocument({ data: datos });
      pdfDoc = await loadingTask.promise;
      totalPaginas = pdfDoc.numPages;
    } catch (e) {
      onError(e);
      throw e;
    }
    desde = Math.max(1, Math.min(totalPaginas, parseInt(desdePedido, 10) || 1));
    hasta = Math.max(desde, Math.min(totalPaginas, parseInt(hastaPedido, 10) || totalPaginas));
    paginaActual = desde;

    // ── Dimensiones de todas las páginas (metadata liviana, sin
    //    renderizar canvas) — necesarias de entrada para poder
    //    reservar el alto correcto de cada placeholder y que el
    //    scroll se comporte bien desde el primer momento. ──
    //    Se piden en lotes concurrentes en vez de una por una (traído del
    //    PR #3): con cientos de páginas, la ida y vuelta serial al worker
    //    de pdf.js era la mayor parte de la espera antes de ver la primera.
    const LOTE_DIMS = 24;
    for (let ini = desde; ini <= hasta; ini += LOTE_DIMS) {
      const fin = Math.min(hasta, ini + LOTE_DIMS - 1);
      const lote = [];
      for (let i = ini; i <= fin; i++) lote.push(pdfDoc.getPage(i));
      const paginas = await Promise.all(lote);
      paginas.forEach((page, k) => {
        const vp = page.getViewport({ scale: 1 });
        dims[ix(ini) + k] = { width: vp.width, height: vp.height };
        page.cleanup && page.cleanup();
      });
    }

    function tamanoEscalado(i) {
      return { width: dims[ix(i)].width * escala, height: dims[ix(i)].height * escala };
    }

    // ── Construir placeholders ──
    for (let i = desde; i <= hasta; i++) {
      const div = document.createElement('div');
      div.className = 'pvcore-page';
      div.dataset.pagina = i;
      const { width, height } = tamanoEscalado(i);
      div.style.width = width + 'px';
      div.style.height = height + 'px';
      // El contenedor suele ser flex en columna: sin esto, mientras la
      // página no tiene canvas adentro se encoge y un irAPagina() temprano
      // (llegada por #pagina / #accion) no tiene dónde scrollear.
      div.style.flexShrink = '0';
      const lbl = document.createElement('div');
      lbl.className = 'pvcore-page-label';
      lbl.textContent = i - desde + 1;
      div.appendChild(lbl);
      contenedor.appendChild(div);
      placeholders.push(div);
      renderState.push('vacio');
    }

    async function renderPagina(i) {
      if (destruido) return;
      if (renderState[ix(i)] === 'renderizando' || renderState[ix(i)] === 'listo') return;
      renderState[ix(i)] = 'renderizando';
      const div = placeholders[ix(i)];
      try {
        const page = await pdfDoc.getPage(i);
        const vp = page.getViewport({ scale: escala });

        // Puede haber cambiado el zoom mientras esto estaba en vuelo —
        // si ya no corresponde a la escala actual, se descarta.
        if (destruido || escala !== vp.scale) { renderState[ix(i)] = 'vacio'; return; }

        const canvas = document.createElement('canvas');
        canvas.width = vp.width;
        canvas.height = vp.height;
        await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;

        const textLayerDiv = document.createElement('div');
        textLayerDiv.className = 'pvcore-textlayer';
        textLayerDiv.style.width = vp.width + 'px';
        textLayerDiv.style.height = vp.height + 'px';
        let capaLista = null;
        try {
          const textContent = await page.getTextContent();
          const tarea = global.pdfjsLib.renderTextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport: vp,
            textDivs: []
          });
          capaLista = tarea && tarea.promise;
        } catch (e) { /* PDF sin capa de texto extraíble (escaneado) — se sigue solo con la imagen */ }

        // Reemplazo atómico: limpiar el placeholder y poner canvas+texto,
        // conservando la etiqueta de página.
        const lbl = div.querySelector('.pvcore-page-label');
        div.innerHTML = '';
        div.appendChild(canvas);
        div.appendChild(textLayerDiv);
        if (lbl) div.appendChild(lbl);
        renderState[ix(i)] = 'listo';
        if (capaLista) capaLista.then(() => { if (renderState[ix(i)] === 'listo' && textLayerDiv.isConnected) onPaginaLista(i, textLayerDiv); }, () => {});
      } catch (e) {
        renderState[ix(i)] = 'vacio';
        div.innerHTML = `<div class="pvcore-page-error">No se pudo renderizar la página ${i}.</div>`;
        onError(e);
      }
    }

    function liberarPagina(i) {
      if (renderState[ix(i)] !== 'listo') return;
      const div = placeholders[ix(i)];
      div.innerHTML = '';
      const lbl = document.createElement('div');
      lbl.className = 'pvcore-page-label';
      lbl.textContent = i - desde + 1;
      div.appendChild(lbl);
      renderState[ix(i)] = 'vacio';
    }

    // ── Virtualización: IntersectionObserver decide qué renderizar,
    //    y se libera lo que quedó lejos de la página actual para no
    //    acumular canvases indefinidamente en documentos largos. ──
    observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const i = parseInt(entry.target.dataset.pagina, 10);
        if (entry.isIntersecting) renderPagina(i);
      });
    }, { root: contenedor, rootMargin: MARGEN_OBSERVER });
    placeholders.forEach(div => observer.observe(div));

    function liberarLejanas() {
      for (let i = desde; i <= hasta; i++) {
        if (Math.abs(i - paginaActual) > VENTANA_RENDER + 4) liberarPagina(i);
      }
    }

    // ── Página actual = la más cercana al centro del viewport ──
    let scrollRaf = null;
    function onScroll() {
      if (scrollRaf) return;
      scrollRaf = requestAnimationFrame(() => {
        scrollRaf = null;
        const mid = contenedor.scrollTop + contenedor.clientHeight / 2;
        let closest = desde, minDist = Infinity;
        placeholders.forEach((div, idx) => {
          const center = div.offsetTop + div.offsetHeight / 2;
          const dist = Math.abs(center - mid);
          if (dist < minDist) { minDist = dist; closest = desde + idx; }
        });
        if (closest !== paginaActual) {
          paginaActual = closest;
          onPaginaVisible(paginaActual, totalPaginas);
          liberarLejanas();
        }
      });
    }
    contenedor.addEventListener('scroll', onScroll);

    // ── Selección de texto → callback con página de origen ──
    function onMouseUp() {
      const sel = global.getSelection();
      const texto = sel ? sel.toString().trim() : '';
      if (!texto) return;
      let node = sel.anchorNode;
      while (node && !(node.classList && node.classList.contains('pvcore-page'))) node = node.parentNode;
      const pagina = node ? parseInt(node.dataset.pagina, 10) : paginaActual;
      onSeleccion(texto, pagina);
    }
    contenedor.addEventListener('mouseup', onMouseUp);

    onPaginaVisible(desde, totalPaginas);
    onListo(totalPaginas);

    // ── API pública ──
    return {
      get totalPaginas() { return totalPaginas; },
      get paginaActual() { return paginaActual; },
      get desde() { return desde; },
      get hasta() { return hasta; },
      getZoom() { return escala; },
      // Texto plano de una página (para el contexto de una cita).
      async textoPagina(n) {
        const page = await pdfDoc.getPage(Math.max(1, Math.min(totalPaginas, n)));
        const tc = await page.getTextContent();
        return tc.items.map(i => i.str + (i.hasEOL ? ' ' : '')).join('').replace(/\s+/g, ' ').trim();
      },
      irAPagina(n) {
        n = enRango(n);
        placeholders[ix(n)].scrollIntoView({ behavior: 'smooth', block: 'start' });
      },
      setZoom(nuevaEscala) {
        nuevaEscala = Math.max(0.4, Math.min(3, nuevaEscala));
        if (nuevaEscala === escala) return;
        escala = nuevaEscala;
        for (let i = desde; i <= hasta; i++) {
          const { width, height } = tamanoEscalado(i);
          placeholders[ix(i)].style.width = width + 'px';
          placeholders[ix(i)].style.height = height + 'px';
          liberarPagina(i);
        }
        // Re-observar fuerza que el IntersectionObserver reconsidere
        // cuáles están dentro del margen ahora que cambiaron de tamaño.
        placeholders.forEach(div => { observer.unobserve(div); observer.observe(div); });
      },
      destruir() {
        destruido = true;
        observer && observer.disconnect();
        contenedor.removeEventListener('scroll', onScroll);
        contenedor.removeEventListener('mouseup', onMouseUp);
      }
    };
  }

  global.PDFViewerCore = { montar };
})(window);
