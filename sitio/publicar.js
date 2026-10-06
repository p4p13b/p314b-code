/* publicar.js — el botón "⚡ publicar" de la propietaria.

   Corre los scripts de Python sin abrir una terminal:

   - En tu máquina, con el taller servido por `python servidor.py`:
     guarda obras/<slug>.json y corre generar_obra.py,
     recalcular_subgrafo.py y los dos de la matriz
     (recalibrar.py, calcular_recorridos.py) y publicar.py, que arma web/.
     Después, "subir a la web" hace git add/commit/push y Cloudflare
     publica web/.
   - En la web o el celular (modo propietaria con token, autor.js):
     guarda obras/<slug>.json en el repo y lanza el workflow de GitHub
     (.github/workflows/publicar.yml), que corre generar_obra.py,
     recalcular_subgrafo.py, los dos de la matriz
     (recalibrar.py, calcular_recorridos.py) y publicar.py, y commitea
     el resultado; Cloudflare publica web/ al ver ese commit.

   Necesita autor.js cargado antes. */
(function () {
  var base = new URL('.', document.currentScript ? document.currentScript.src : location.href);

  var css = document.createElement('style');
  css.textContent =
    '.pub-caja{position:fixed;right:16px;bottom:16px;width:min(560px,calc(100vw - 32px));max-height:min(70vh,560px);display:flex;flex-direction:column;' +
    'background:var(--bg,#080808);color:var(--ink,#f5f5f5);border:1px solid var(--rule,#292929);border-radius:3px;box-shadow:0 10px 40px rgba(0,0,0,.5);z-index:10000;font-family:var(--font-mono,monospace)}' +
    '.pub-cab{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--rule,#292929);font-size:11px;letter-spacing:.1em;text-transform:uppercase}' +
    '.pub-cab .pub-est{margin-left:auto;text-transform:none;letter-spacing:0;color:var(--ink-muted,#8a8a8a)}' +
    '.pub-cab button{font:inherit;color:var(--ink-muted,#8a8a8a);background:none;border:none;cursor:pointer;padding:2px 4px}' +
    '.pub-log{margin:0;padding:12px 14px;overflow:auto;font-size:11px;line-height:1.6;white-space:pre-wrap;word-break:break-word;color:var(--ink-soft,#d0d0d0);flex:1}' +
    '.pub-pie{display:flex;gap:8px;padding:10px 14px;border-top:1px solid var(--rule,#292929);flex-wrap:wrap}' +
    '.pub-pie:empty{display:none}' +
    '.pub-pie button,.pub-pie a{font:inherit;font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:8px 12px;border:1px solid var(--rule,#292929);border-radius:3px;background:var(--page,#0d0d0d);color:var(--ink-soft,#d0d0d0);cursor:pointer;text-decoration:none}' +
    '.pub-ok{color:var(--green,#22c55e)!important}.pub-mal{color:var(--red,#ef4444)!important}';
  document.head.appendChild(css);

  function caja(titulo) {
    var viejo = document.querySelector('.pub-caja'); if (viejo) viejo.remove();
    var el = document.createElement('div');
    el.className = 'pub-caja'; el.setAttribute('role', 'status');
    el.innerHTML = '<div class="pub-cab"><span></span><span class="pub-est">…</span><button title="cerrar">×</button></div><pre class="pub-log"></pre><div class="pub-pie"></div>';
    el.querySelector('.pub-cab span').textContent = titulo;
    el.querySelector('.pub-cab button').onclick = function () { el.remove(); };
    document.body.appendChild(el);
    var pre = el.querySelector('.pub-log'), est = el.querySelector('.pub-est');
    return {
      log: function (t) { pre.textContent += t + (/\n$/.test(t) ? '' : '\n'); pre.scrollTop = pre.scrollHeight; },
      estado: function (t, cls) { est.textContent = t; est.className = 'pub-est' + (cls ? ' ' + cls : ''); },
      boton: function (texto, fn, href) {
        var b = document.createElement(href ? 'a' : 'button');
        b.textContent = texto;
        if (href) { b.href = href; b.target = '_blank'; b.rel = 'noopener'; } else b.onclick = fn;
        el.querySelector('.pub-pie').appendChild(b);
        return b;
      },
      limpiarBotones: function () { el.querySelector('.pub-pie').innerHTML = ''; }
    };
  }

  // ── servidor local (servidor.py) ──
  async function local(ruta, cuerpo) {
    var r = await fetch(new URL('api/' + ruta, base).href, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-P314B': '1' },
      body: JSON.stringify(cuerpo || {})
    });
    var d = null;
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || !d) throw new Error((d && d.error) || ('el servidor respondió ' + r.status));
    return d;
  }
  var hayServidor = null;
  async function servidorLocal() {
    if (hayServidor !== null) return hayServidor;
    try { hayServidor = !!(await local('estado')).ok; } catch (e) { hayServidor = false; }
    return hayServidor;
  }

  function dormir(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function seguirWorkflow(c, desde) {
    c.log('Esperando que GitHub arranque la publicación…');
    var run = null, ultimo = '';
    for (var i = 0; i < 150; i++) {            // hasta ~12 minutos
      await dormir(i < 6 ? 3000 : 5000);
      run = await window.P314B.estadoPublicacion(desde);
      if (!run) continue;
      var st = run.status + (run.conclusion ? ' · ' + run.conclusion : '');
      if (st !== ultimo) { c.log('GitHub: ' + st.replace('queued', 'en cola').replace('in_progress', 'corriendo').replace('completed', 'terminado')); ultimo = st; }
      if (run.status === 'completed') break;
    }
    if (run) c.boton('ver en GitHub', null, run.html_url);
    if (run && run.conclusion === 'success') {
      c.estado('✓ publicado', 'pub-ok');
      c.log('\n✓ Listo: los scripts corrieron y se guardó web/. Cloudflare lo publica en uno o dos minutos.');
      c.boton('ver el sitio', null, new URL('index.html', base).href);
      return true;
    }
    c.estado(run ? '✗ falló' : 'sin respuesta', 'pub-mal');
    c.log(run ? '\n✗ La publicación falló. En "ver en GitHub" está el detalle de qué script se quejó.' : '\nGitHub no confirmó el arranque. Mirá la pestaña Actions del repo.');
    return false;
  }

  async function subirLocal(c) {
    c.limpiarBotones();
    c.estado('subiendo…');
    c.log('\n$ git add sitio web && git commit && git push');
    try {
      var d = await local('subir', {});
      c.log(d.log || '');
      c.estado(d.ok ? '✓ subido' : '✗ falló', d.ok ? 'pub-ok' : 'pub-mal');
      if (d.ok) c.log('\n✓ En GitHub. La web se actualiza sola en uno o dos minutos.');
    } catch (e) {
      c.estado('✗ falló', 'pub-mal'); c.log('✗ ' + e.message);
    }
  }

  /* Publica una obra (slug + el objeto que exporta el taller), o todo
     el sitio si slug es null. Devuelve true si terminó bien. */
  async function publicar(slug, obra) {
    var P = window.P314B;
    if (!P || !P.autor) { alert('Publicar es solo para la propietaria.'); return false; }
    var c = caja(slug ? 'publicar · ' + slug : 'regenerar y publicar todo');
    try {
      if (P.modo === 'local') {
        if (!(await servidorLocal())) {
          c.estado('falta el servidor', 'pub-mal');
          c.log('Para publicar con un botón, cerrá "python -m http.server" y abrí el sitio con:\n\n    python servidor.py\n\ndesde la carpeta sitio/ (es lo mismo, más el botón). Mientras tanto: "↓ descargar .json" y los scripts a mano.');
          return false;
        }
        c.estado('corriendo…');
        c.log(slug ? 'Guardando obras/' + slug + '.json y corriendo los scripts…' : 'Regenerando todas las obras…');
        var d = await local(slug ? 'publicar' : 'regenerar', slug ? { slug: slug, obra: obra } : {});
        c.log(d.log || '');
        if (!d.ok) { c.estado('✗ falló', 'pub-mal'); c.log('\n✗ Un script se negó (arriba dice cuál y por qué). No se subió nada.'); return false; }
        c.estado('✓ generado', 'pub-ok');
        c.log('\n✓ Generado en tu máquina. Para que se vea en la web:');
        c.boton('⬆ subir a la web', function () { subirLocal(c); });
        c.boton('ver la obra', null, new URL(slug ? 'obras/' + slug + '.html' : 'index.html', base).href);
        return true;
      }
      if (P.modo === 'web') {
        c.estado('guardando…');
        if (slug) {
          c.log('Guardando obras/' + slug + '.json en el repo…');
          var sha = await P.escribirArchivo('obras/' + slug + '.json', JSON.stringify(obra, null, 2) + '\n', 'taller: obras/' + slug + '.json [skip ci]');
          c.log('✓ guardado (' + sha.slice(0, 7) + ')');
        }
        c.estado('publicando…');
        c.log('Lanzando la publicación en GitHub (generar_obra.py, recalcular_subgrafo.py, matriz, publicar.py)…');
        var desde = await P.dispararPublicacion(slug || '');
        return await seguirWorkflow(c, desde);
      }
    } catch (e) {
      c.estado('✗ error', 'pub-mal');
      c.log('✗ ' + e.message);
    }
    return false;
  }

  /* Saca una obra del sitio. modo 'ocultar': le saca el tilde "mostrar
     en el sitio web" (sigue en el taller). modo 'eliminar': la manda a
     papelera/ (recuperable) y la borra de corpus y acciones. Después
     regenera todo. */
  // slug: uno o varios (lista). Varios van en una sola corrida: el
  // workflow los procesa en orden y sigue aunque alguno no se pueda.
  async function sacar(slug, modo) {
    var P = window.P314B;
    if (!P || !P.autor) { alert('Esto es solo para la propietaria.'); return false; }
    var slugs = Array.isArray(slug) ? slug : [slug];
    slug = slugs.join(' ');
    var c = caja((modo === 'eliminar' ? 'eliminar · ' : 'quitar de la web · ') + (slugs.length > 1 ? slugs.length + ' obras' : slug));
    try {
      if (P.modo === 'local') {
        if (!(await servidorLocal())) {
          c.estado('falta el servidor', 'pub-mal');
          c.log('Abrí el sitio con "python servidor.py" (desde sitio/) o corré a mano:\n\n' + slugs.map(function (x) { return '    python eliminar_obra.py ' + x + (modo === 'eliminar' ? '' : ' --ocultar'); }).join('\n'));
          return false;
        }
        c.estado('corriendo…');
        var d = await local('eliminar', { slugs: slugs, modo: modo });
        c.log(d.log || '');
        if (!d.ok) { c.estado('✗ no se hizo', 'pub-mal'); c.log('\n✗ Arriba dice por qué. No se subió nada.'); return false; }
        c.estado('✓ hecho', 'pub-ok');
        c.log('\n✓ Hecho en tu máquina. Para que se vea en la web:');
        c.boton('⬆ subir a la web', function () { subirLocal(c); });
        return true;
      }
      c.estado('publicando…');
      c.log('Lanzando en GitHub: eliminar_obra.py' + (modo === 'eliminar' ? '' : ' --ocultar') + ' y regenerar todo…');
      var desde = await P.dispararPublicacion('', { slug: slug, modo: modo });
      return await seguirWorkflow(c, desde);
    } catch (e) {
      c.estado('✗ error', 'pub-mal');
      c.log('✗ ' + e.message);
    }
    return false;
  }

  /* Actualizar todo: lanza .github/workflows/actualizar.yml, que corre en
     orden la matriz, la superficie (con las familias de palabras), los
     scripts que antes iban a mano (archivo, términos, terceros) y la
     publicación con el deploy. Tarda de 20 minutos a un par de horas (la
     matriz es lo largo). Se puede cerrar la página: sigue en GitHub, y al
     volver a apretar el botón se retoma el seguimiento en vez de lanzar
     otra. */
  var CLAVE_ACT = 'p314b_actualizar_desde';
  async function actualizarTodo() {
    var P = window.P314B;
    if (!P || !P.autor) { alert('Esto es solo para la propietaria.'); return false; }
    var c = caja('actualizar todo');
    if (P.modo !== 'web') {
      c.estado('solo en la web', 'pub-mal');
      c.log('«Actualizar todo» corre en GitHub (la matriz necesita el modelo y la caché que viven ahí).\n\nAbrí el taller en la web, con tu token, y apretalo ahí; o en GitHub: Actions → «Actualizar todo» → Run workflow.');
      return false;
    }
    try {
      var desde = null, run = null;
      try { desde = localStorage.getItem(CLAVE_ACT); } catch (e) {}
      if (desde) run = await P.estadoWorkflow('actualizar.yml', desde);
      if (run && run.status !== 'completed') {
        c.log('Ya hay una actualización en curso (lanzada ' + new Date(run.created_at).toLocaleString('es-AR') + '): sigo esa.');
      } else {
        c.estado('lanzando…');
        c.log('Lanzando en GitHub, en orden:\n  1 · matriz (propuestas y recorridos)\n  2 · superficie, anexo y familias de palabras\n  3 · archivo, términos y terceros\n  4 · publicar y desplegar\n\nPuede tardar de 20 minutos a un par de horas. Podés cerrar esta página: sigue igual.');
        desde = await P.dispararWorkflow('actualizar.yml');
        try { localStorage.setItem(CLAVE_ACT, desde); } catch (e) {}
        run = null;
      }
      var hechos = {}, ultimo = '', enlace = false;
      for (var i = 0; i < 1200; i++) {          // hasta ~6 horas
        if (i) await dormir(i < 10 ? 4000 : 15000);
        run = await P.estadoWorkflow('actualizar.yml', desde);
        if (!run) { if (i > 30) break; continue; }
        if (!enlace) { c.boton('ver en GitHub', null, run.html_url); enlace = true; }
        (run.pasos || []).forEach(function (st) {
          if (!/^\d ·/.test(st.name)) return;
          if (st.status === 'completed' && !hechos[st.name]) {
            hechos[st.name] = 1;
            c.log((st.conclusion === 'success' ? '✓ ' : st.conclusion === 'skipped' ? '· ' : '✗ ') + st.name);
          }
        });
        var actual = (run.pasos || []).filter(function (st) { return st.status === 'in_progress'; })[0];
        var est = run.status === 'completed' ? '' : actual ? actual.name : (run.status === 'queued' ? 'en cola' : 'corriendo');
        if (est && est !== ultimo) { c.estado(est + '…'); ultimo = est; }
        if (run.status === 'completed') break;
      }
      if (run && run.status === 'completed' && run.conclusion === 'success') {
        c.estado('✓ al día', 'pub-ok');
        c.log('\n✓ Listo: todo recalculado y publicado. Cloudflare lo sirve en uno o dos minutos.');
        c.boton('ver el sitio', null, new URL('index.html', base).href);
        try { localStorage.removeItem(CLAVE_ACT); } catch (e) {}
        return true;
      }
      if (run && run.status === 'completed') {
        c.estado('✗ se cortó', 'pub-mal');
        c.log('\n✗ Se cortó en el paso marcado con ✗. En «ver en GitHub» está el detalle. El sitio quedó como estaba.');
        try { localStorage.removeItem(CLAVE_ACT); } catch (e) {}
        return false;
      }
      c.estado(run ? 'sigue en GitHub' : 'sin respuesta', run ? '' : 'pub-mal');
      c.log(run ? '\nSigue corriendo en GitHub. Volvé a apretar «actualizar todo» para ver cómo va.' : '\nGitHub no confirmó el arranque. Mirá la pestaña Actions del repo.');
    } catch (e) {
      c.estado('✗ error', 'pub-mal');
      c.log('✗ ' + e.message);
    }
    return false;
  }

  window.Publicar = { publicar: publicar, sacar: sacar, servidorLocal: servidorLocal, actualizarTodo: actualizarTodo };
})();
