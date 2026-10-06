/* autor.js — modo propietario (escritora/editora) del sitio p314b.

   Dos formas de ser propietaria; un visitante no tiene ninguna:

   1. En tu máquina (localhost, 127.0.0.1 o file://): siempre.
   2. En la web o el celular: con un token de GitHub guardado en ESE
      navegador desde acceso.html. El token se verifica contra la API de
      GitHub: solo vale si tiene permiso de escritura sobre el repo. Sin
      token válido no hay botón, parámetro ni clave que abra nada.

   En modo web, las herramientas (taller, matriz) leen los datos directo
   del repo por la API (siempre la última versión de main, no la copia
   publicada) y escriben ahí con el mismo token. Ver publicar.js y
   .github/workflows/publicar.yml.

   Uso en una página:
     <script src="autor.js"></script>              en el <head>, sin defer
     class="solo-autor"                              se oculta a visitantes
     window.P314B.autor / window.P314B.listo         (true/false, Promise)
     <script src="autor.js" data-herramienta>        herramienta: sin
                                                     permiso, vuelve al índice */
(function () {
  var REPO = { owner: 'p4p13b', repo: 'p314b', rama: 'main', carpeta: 'sitio' };
  var CLAVE_TOKEN = 'p314b_gh_token';
  var CLAVE_OK = 'p314b_gh_ok';
  var VIGENCIA_MS = 12 * 60 * 60 * 1000;

  var h = location.hostname;
  var local = location.protocol === 'file:' ||
    h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1' || h === '';

  function leer(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function poner(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }

  var yo = document.currentScript;
  var herramienta = !!(yo && yo.hasAttribute('data-herramienta'));
  // Raíz del sitio = carpeta donde está autor.js (www.p314b.space: /).
  var base = new URL('.', yo ? yo.src : location.href);

  var token = local ? null : leer(CLAVE_TOKEN);
  var huella = token ? token.slice(-6) : '';
  var cache = null;
  try { cache = JSON.parse(leer(CLAVE_OK) || 'null'); } catch (e) {}
  var verificadoReciente = !!(token && cache && cache.huella === huella && Date.now() - cache.t < VIGENCIA_MS);

  var modo = local ? 'local' : (token ? 'web' : null);
  var autor = local || verificadoReciente;

  var css = document.createElement('style');
  css.textContent =
    'html:not(.modo-autor) .solo-autor{display:none !important}' +
    'html.autor-verificando body{visibility:hidden}';
  document.head.appendChild(css);
  if (autor) document.documentElement.classList.add('modo-autor');

  function salir() {
    document.documentElement.classList.remove('modo-autor', 'autor-verificando');
    if (herramienta) location.replace(new URL('index.html', base).href);
  }

  // ── API de GitHub con el token (solo modo web) ──
  function api(ruta, opts) {
    opts = opts || {};
    var headers = Object.assign({
      'Accept': 'application/vnd.github+json',
      'Authorization': 'Bearer ' + token,
      'X-GitHub-Api-Version': '2022-11-28'
    }, opts.headers || {});
    return window.__fetchOriginal('https://api.github.com' + ruta, Object.assign({}, opts, { headers: headers }));
  }
  // Qué quiere decir cada error de GitHub, en castellano.
  function explicar(status, que) {
    if (status === 401) return 'GitHub rechazó el token (' + que + '): venció o lo revocaste. Sacá uno nuevo y pegalo en acceso.html.';
    if (status === 403 || status === 404) return 'El token no tiene permiso para ' + que + ' (GitHub ' + status + '). En GitHub, editá el token: Repository access = p314b; Permissions → Contents = Read and write y Actions = Read and write. Después volvé a pegarlo en acceso.html.';
    if (status === 409 || status === 422) return 'GitHub no aceptó ' + que + ' (' + status + '): probablemente el archivo cambió mientras tanto. Volvé a apretar publicar.';
    return 'GitHub respondió ' + status + ' al ' + que + '.';
  }
  function rutaRepo(rel) { return REPO.carpeta + '/' + rel.replace(/^\/+/, ''); }
  function b64(texto) {
    // texto: un string, o los bytes de un archivo (ArrayBuffer/Uint8Array: un PDF)
    var bytes = typeof texto === 'string' ? new TextEncoder().encode(texto) : new Uint8Array(texto), bin = '';
    for (var i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }
  async function escribirArchivo(rel, contenido, mensaje) {
    var ruta = '/repos/' + REPO.owner + '/' + REPO.repo + '/contents/' + rutaRepo(rel).split('/').map(encodeURIComponent).join('/');
    // La versión actual (sha) se lee siempre sin caché: el navegador puede
    // guardar esta respuesta hasta 60 s y, al publicar dos veces seguidas,
    // mandaba una versión vieja (409). Si igual choca, se relee y se
    // reintenta una vez.
    var r;
    for (var intento = 0; intento < 2; intento++) {
      var sha;
      var r0 = await api(ruta + '?ref=' + REPO.rama + '&t=' + Date.now(), { cache: 'no-store' });
      if (r0.ok) sha = (await r0.json()).sha;
      else if (r0.status !== 404) throw new Error(explicar(r0.status, 'leer ' + rel));
      r = await api(ruta, { method: 'PUT', body: JSON.stringify({ message: mensaje, content: b64(contenido), branch: REPO.rama, sha: sha }) });
      if (r.ok || (r.status !== 409 && r.status !== 422)) break;
      await new Promise(function (ok) { setTimeout(ok, 1200); });
    }
    if (!r.ok) { avisarToken(r.status); throw new Error(explicar(r.status, 'guardar ' + rel + ' (permiso Contents)')); }
    return (await r.json()).commit.sha;
  }
  // Lee un archivo de trabajo del repo (última versión de main), como texto.
  async function leerArchivo(rel) {
    var ruta = '/repos/' + REPO.owner + '/' + REPO.repo + '/contents/' + rutaRepo(rel).split('/').map(encodeURIComponent).join('/') + '?ref=' + REPO.rama + '&t=' + Date.now();
    var r = await api(ruta, { headers: { 'Accept': 'application/vnd.github.raw' }, cache: 'no-store' });
    if (!r.ok) { avisarToken(r.status); throw new Error(explicar(r.status, 'leer ' + rel)); }
    return r.text();
  }
  // Nombres de los archivos de una carpeta del sitio (p. ej. las láminas).
  async function listarCarpeta(rel) {
    var ruta = '/repos/' + REPO.owner + '/' + REPO.repo + '/contents/' + rutaRepo(rel).split('/').map(encodeURIComponent).join('/') + '?ref=' + REPO.rama + '&t=' + Date.now();
    var r = await api(ruta, { cache: 'no-store' });
    if (r.status === 404) return [];
    if (!r.ok) { avisarToken(r.status); throw new Error(explicar(r.status, 'leer la carpeta ' + rel)); }
    var d = await r.json();
    return Array.isArray(d) ? d.filter(function (x) { return x.type === 'file'; }).map(function (x) { return x.name; }) : [];
  }
  // Borra un archivo de la papelera del repo (lo pide la autora desde
  // «guardadas» en el taller). Solo papelera/*.json: nada más se borra así.
  async function borrarArchivo(rel, mensaje) {
    if (!/^papelera\/[^\/]+\.json$/.test(rel)) throw new Error('solo se pueden borrar archivos de la papelera: ' + rel);
    var ruta = '/repos/' + REPO.owner + '/' + REPO.repo + '/contents/' + rutaRepo(rel).split('/').map(encodeURIComponent).join('/');
    var r0 = await api(ruta + '?ref=' + REPO.rama + '&t=' + Date.now(), { cache: 'no-store' });
    if (r0.status === 404) return null;          // ya no estaba
    if (!r0.ok) { avisarToken(r0.status); throw new Error(explicar(r0.status, 'leer ' + rel)); }
    var r = await api(ruta, { method: 'DELETE', body: JSON.stringify({ message: mensaje, sha: (await r0.json()).sha, branch: REPO.rama }) });
    if (!r.ok) { avisarToken(r.status); throw new Error(explicar(r.status, 'borrar ' + rel + ' (permiso Contents)')); }
    return (await r.json()).commit.sha;
  }
  async function dispararPublicacion(obra, sacar) {
    // sacar: { slug, modo: 'ocultar' | 'eliminar' } para quitar una obra.
    var desde = new Date(Date.now() - 5000).toISOString();
    var inputs = { obra: obra || '' };
    if (sacar) { inputs.eliminar = sacar.slug; inputs.modo = sacar.modo; }
    var r = await api('/repos/' + REPO.owner + '/' + REPO.repo + '/actions/workflows/publicar.yml/dispatches', {
      method: 'POST', body: JSON.stringify({ ref: REPO.rama, inputs: inputs })
    });
    if (!r.ok) throw new Error(explicar(r.status, 'lanzar la publicación (permiso Actions)'));
    return desde;
  }
  async function estadoPublicacion(desde) {
    var r = await api('/repos/' + REPO.owner + '/' + REPO.repo + '/actions/workflows/publicar.yml/runs?event=workflow_dispatch&per_page=5');
    if (!r.ok) return null;
    var runs = ((await r.json()).workflow_runs || []).filter(function (x) { return x.created_at >= desde.slice(0, 19); });
    return runs[0] || null;
  }

  // Cualquier workflow (actualizar.yml: «actualizar todo»), y su estado
  // con los pasos del job que está corriendo.
  async function dispararWorkflow(archivo, inputs) {
    var desde = new Date(Date.now() - 5000).toISOString();
    var r = await api('/repos/' + REPO.owner + '/' + REPO.repo + '/actions/workflows/' + archivo + '/dispatches', {
      method: 'POST', body: JSON.stringify({ ref: REPO.rama, inputs: inputs || {} })
    });
    if (!r.ok) throw new Error(explicar(r.status, 'lanzar ' + archivo + ' (permiso Actions)'));
    return desde;
  }
  async function estadoWorkflow(archivo, desde) {
    var r = await api('/repos/' + REPO.owner + '/' + REPO.repo + '/actions/workflows/' + archivo + '/runs?event=workflow_dispatch&per_page=5', { cache: 'no-store' });
    if (!r.ok) return null;
    var run = ((await r.json()).workflow_runs || []).filter(function (x) { return x.created_at >= desde.slice(0, 19); })[0];
    if (!run) return null;
    var j = await api('/repos/' + REPO.owner + '/' + REPO.repo + '/actions/runs/' + run.id + '/jobs', { cache: 'no-store' });
    run.pasos = j.ok ? (((await j.json()).jobs || [])[0] || {}).steps || [] : [];
    return run;
  }

  // En modo web, las HERRAMIENTAS (taller, matriz) leen los archivos de
  // trabajo del repo por la API (la última versión de main: web/ no los
  // tiene). Las páginas públicas (índice, obras) leen lo publicado, igual
  // que un visitante. Los PDF siguen viniendo del sitio.
  window.__fetchOriginal = window.fetch.bind(window);
  // Un 401/403 de GitHub es casi siempre el token (vencido o sin el
  // permiso Contents/Actions): se avisa una vez, con el camino al arreglo.
  var avisado = false;
  function avisarToken(status) {
    if (avisado || (status !== 401 && status !== 403)) return;
    avisado = true;
    var pintar = function () {
      var el = document.createElement('div');
      el.setAttribute('role', 'alert');
      el.style.cssText = 'position:fixed;left:12px;right:12px;bottom:12px;z-index:10001;max-width:620px;margin:0 auto;padding:12px 14px;' +
        'background:#2a1210;color:#ffd9d4;border:1px solid #ef4444;border-radius:4px;font:13px/1.5 ui-monospace,monospace';
      el.innerHTML = 'GitHub rechazó el token (' + status + '): no puede leer o guardar los archivos del sitio. ' +
        '<a href="' + new URL('acceso.html', base).href + '" style="color:#fff">Abrí acceso y tocá "probar permisos del token"</a>. ' +
        '<button style="float:right;background:none;border:0;color:#ffd9d4;cursor:pointer">×</button>';
      el.querySelector('button').onclick = function () { el.remove(); };
      document.body.appendChild(el);
    };
    if (document.body) pintar(); else document.addEventListener('DOMContentLoaded', pintar);
  }
  if (modo === 'web' && herramienta) {
    window.fetch = function (entrada, opts) {
      try {
        var url = new URL(typeof entrada === 'string' ? entrada : entrada.url, location.href);
        if (url.origin === location.origin && url.pathname.indexOf(base.pathname) === 0 && !/\.pdf$/i.test(url.pathname)) {
          var rel = decodeURIComponent(url.pathname.slice(base.pathname.length)) || 'index.html';
          var ruta = '/repos/' + REPO.owner + '/' + REPO.repo + '/contents/' + rutaRepo(rel).split('/').map(encodeURIComponent).join('/') + '?ref=' + REPO.rama;
          // Si el token venció o no alcanza, se lee la copia publicada:
          // el sitio nunca se rompe por un token viejo.
          return api(ruta, { headers: { 'Accept': 'application/vnd.github.raw' }, cache: 'no-store' })
            .then(function (r) { if (!r.ok) avisarToken(r.status); return r.ok ? r : window.__fetchOriginal(entrada, opts); },
                  function () { return window.__fetchOriginal(entrada, opts); });
        }
      } catch (e) {}
      return window.__fetchOriginal(entrada, opts);
    };
  }

  var listo;
  if (local) listo = Promise.resolve(true);
  else if (!token) {
    listo = Promise.resolve(false);
    if (herramienta) salir();
  } else if (verificadoReciente) listo = Promise.resolve(true);
  else {
    if (herramienta) document.documentElement.classList.add('autor-verificando');
    listo = api('/repos/' + REPO.owner + '/' + REPO.repo).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var ok = !!(d && d.permissions && d.permissions.push);
        if (ok) {
          poner(CLAVE_OK, JSON.stringify({ t: Date.now(), huella: huella }));
          document.documentElement.classList.add('modo-autor');
          document.documentElement.classList.remove('autor-verificando');
          window.P314B.autor = true;
        } else {
          poner(CLAVE_OK, null);
          salir();
        }
        return ok;
      }, function () { salir(); return false; });
  }

  window.P314B = {
    autor: autor,
    modo: modo,          // 'local' | 'web' | null
    listo: listo,
    repo: REPO,
    guardarToken: function (t) { poner(CLAVE_TOKEN, t); poner(CLAVE_OK, null); },
    olvidarToken: function () { poner(CLAVE_TOKEN, null); poner(CLAVE_OK, null); },
    escribirArchivo: escribirArchivo,
    leerArchivo: leerArchivo,
    listarCarpeta: listarCarpeta,
    borrarArchivo: borrarArchivo,
    dispararPublicacion: dispararPublicacion,
    estadoPublicacion: estadoPublicacion,
    dispararWorkflow: dispararWorkflow,
    estadoWorkflow: estadoWorkflow
  };
  window.P314B_AUTOR = autor; // compatibilidad
})();
