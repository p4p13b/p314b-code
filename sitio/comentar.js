/* comentar.js — «comentar» en cualquier parte del sitio.

   Un clic sostenido (o un toque largo en el celular) sobre cualquier lugar
   que no sea un enlace o un botón abre un cuadro para dejar un comentario
   sobre lo que sea. No es «dejar una frase» (esa va cifrada al correo de la
   autora, sobre un pasaje): esto llega al Worker (worker/comentarios.js),
   sin correo de por medio, y guarda de qué página vino.

   Privado por defecto. Con «que se publique» entra en la cola de la
   autora y, si ella lo aprueba, se lee en comentarios.html, aparte de los
   textos. No pide datos. Hay un campo de firma que no se sugiere ni se
   prohíbe: si alguien firma, la firma va con el comentario, también en
   un privado. Antes de enviar, el navegador hace un cálculo
   corto (prueba de trabajo) para frenar a los robots.

   Lo carga visita.js en todas las páginas del lector. Una zona donde no
   deba abrirse lleva data-sin-comentario. */
(function () {
  'use strict';
  if (window.__p314bComentar) return;
  window.__p314bComentar = true;
  try { if (document.documentElement.classList.contains('en-panel') || window.top !== window) return; } catch (e) { return; }

  var ESPERA = 650;       // ms sostenidos para abrir
  var TOLERANCIA = 8;     // px de movimiento antes de que cuente como arrastrar o seleccionar
  var BITS = 16;          // igual que worker/comentarios.js
  var base = new URL('.', (document.currentScript && document.currentScript.src) || location.href);
  var NO = 'a,button,input,textarea,select,label,summary,option,video,audio,iframe,[contenteditable=""],[contenteditable="true"],[role="button"],[role="dialog"],[data-sin-comentario],.p314b-com';

  var css = document.createElement('style');
  css.textContent =
    '.p314b-com-anillo{position:fixed;z-index:2147483000;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;pointer-events:none;' +
      'border:1.5px solid var(--mark-lt,#60a5fa);opacity:0;transform:scale(.3);transition:opacity .2s,transform ' + (ESPERA - 150) + 'ms linear}' +
    '.p314b-com-anillo.on{opacity:.9;transform:scale(1)}' +
    '.p314b-com{position:fixed;z-index:2147483001;width:min(380px,calc(100vw - 32px));box-sizing:border-box;padding:16px 16px 14px;' +
      'background:var(--page,#0d0d0d);color:var(--ink,#f5f5f5);border:1px solid var(--rule,#333);border-radius:4px;' +
      'box-shadow:0 12px 40px rgba(0,0,0,.45);font-family:var(--font-body,Georgia,serif);font-size:15px;line-height:1.45}' +
    '.p314b-com *{box-sizing:border-box}' +
    '.p314b-com h2{margin:0 0 10px;font:500 11px/1 var(--font-mono,ui-monospace,monospace);letter-spacing:.2em;text-transform:uppercase;color:var(--ink-muted,#8a8a8a);border:0;padding:0}' +
    '.p314b-com textarea,.p314b-com input[type=text]{display:block;width:100%;margin:0 0 10px;padding:8px 9px;font:inherit;color:inherit;background:transparent;border:1px solid var(--line-ctl,#555);border-radius:3px}' +
    '.p314b-com textarea{min-height:110px;resize:vertical}' +
    '.p314b-com label.c{display:flex;gap:8px;align-items:flex-start;margin:0 0 8px;font-size:13.5px;color:var(--ink-soft,#d0d0d0);cursor:pointer}' +
    '.p314b-com label.c input{margin-top:3px}' +
    '.p314b-com .trampa{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}' +
    '.p314b-com .fila{display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:6px}' +
    '.p314b-com button{font:13px var(--font-mono,ui-monospace,monospace);color:inherit;padding:7px 12px;min-height:34px;background:transparent;border:1px solid var(--line-ctl,#555);border-radius:3px;cursor:pointer}' +
    '.p314b-com button.si{border-color:var(--ink,#f5f5f5)}' +
    '.p314b-com button:disabled{opacity:.5;cursor:default}' +
    '.p314b-com :focus-visible{outline:2px solid var(--mark-lt,#60a5fa);outline-offset:2px}' +
    '.p314b-com .nota{margin:8px 0 0;font:11.5px/1.6 var(--font-mono,ui-monospace,monospace);color:var(--ink-muted,#8a8a8a)}' +
    '.p314b-com .nota a{color:inherit}' +
    '.p314b-com .estado{margin:6px 0 0;min-height:1.4em;font:12px/1.5 var(--font-mono,ui-monospace,monospace);color:var(--ink-soft,#d0d0d0)}' +
    '@media (max-width:560px){.p314b-com{left:16px !important;right:16px;top:auto !important;bottom:16px;width:auto}}';
  document.head.appendChild(css);

  var anillo = null, timer = 0, ini = null, abierto = null, tragarClic = 0;

  function cancelar() {
    clearTimeout(timer); timer = 0; ini = null;
    if (anillo) anillo.classList.remove('on');
  }

  document.addEventListener('pointerdown', function (e) {
    if (abierto && abierto.contains(e.target)) return;
    if (e.button !== 0 || !e.isPrimary) return;
    if (e.target.closest && e.target.closest(NO)) return;
    cancelar();
    ini = { x: e.clientX, y: e.clientY, tipo: e.pointerType };
    if (!anillo) { anillo = document.createElement('div'); anillo.className = 'p314b-com-anillo'; anillo.setAttribute('aria-hidden', 'true'); document.body.appendChild(anillo); }
    anillo.style.left = e.clientX + 'px'; anillo.style.top = e.clientY + 'px';
    // el anillo aparece recién después de un momento: un clic común no lo muestra
    var mostrar = setTimeout(function () { if (ini) anillo.classList.add('on'); }, 150);
    timer = setTimeout(function () {
      clearTimeout(mostrar);
      var p = ini; cancelar();
      if (!p) return;
      // si en el camino se seleccionó texto, era una selección, no un comentario
      var sel = window.getSelection && window.getSelection();
      if (sel && String(sel).trim() && p.tipo === 'mouse') return;
      if (sel && p.tipo !== 'mouse') try { sel.removeAllRanges(); } catch (er) {}
      tragarClic = Date.now() + 1200;
      abrir(p.x, p.y);
    }, ESPERA);
  }, true);
  document.addEventListener('pointermove', function (e) {
    if (ini && Math.hypot(e.clientX - ini.x, e.clientY - ini.y) > TOLERANCIA) cancelar();
  }, true);
  ['pointerup', 'scroll', 'dragstart'].forEach(function (t) { document.addEventListener(t, function () { if (ini) cancelar(); }, true); });
  // en el celular el navegador se queda con el toque largo (pointercancel) y
  // dispara contextmenu: ahí se abre el cuadro en vez del menú
  document.addEventListener('pointercancel', function () { if (ini && ini.tipo === 'mouse') cancelar(); }, true);
  // lo que sigue al clic sostenido (el clic, el menú del toque largo) no hace nada más
  document.addEventListener('click', function (e) {
    if (Date.now() < tragarClic && !(abierto && abierto.contains(e.target))) { e.preventDefault(); e.stopPropagation(); tragarClic = 0; }
  }, true);
  document.addEventListener('contextmenu', function (e) {
    if (ini && ini.tipo !== 'mouse') {
      e.preventDefault();
      var p = ini; cancelar();
      try { window.getSelection().removeAllRanges(); } catch (er) {}
      tragarClic = Date.now() + 1200;
      abrir(p.x, p.y);
    } else if (ini || Date.now() < tragarClic) e.preventDefault();
  }, true);

  function abrir(x, y) {
    cerrar();
    var antes = document.activeElement;
    var f = document.createElement('form');
    f.className = 'p314b-com';
    f.setAttribute('role', 'dialog');
    f.setAttribute('aria-label', 'dejar un comentario');
    f.noValidate = true;
    f.innerHTML =
      '<h2>comentario</h2>' +
      '<textarea name="texto" maxlength="1500" aria-label="tu comentario" placeholder="sobre lo que sea: esta página, el sitio, algo que viste"></textarea>' +
      '<input type="text" name="firma" maxlength="60" autocomplete="off" placeholder="firma" aria-label="firma">' +
      '<label class="c"><input type="checkbox" name="publico"> que se publique (la autora lo lee antes; si lo aprueba, aparece en comentarios, aparte de los textos)</label>' +
      '<label class="c"><input type="checkbox" name="matriz"> que sirva, sin publicarse, para estudiar cómo se lee la obra</label>' +
      '<div class="trampa" aria-hidden="true"><label>web <input type="text" name="web" tabindex="-1" autocomplete="off"></label></div>' +
      '<div class="fila"><button type="button" data-cerrar>cancelar</button><button type="submit" class="si">enviar</button></div>' +
      '<p class="estado" role="status" aria-live="polite"></p>' +
      '<p class="nota">No pide datos tuyos. Si es privado lo lee solo la autora. Correos y teléfonos se tachan. <a href="' + new URL('comentarios.html', base).href + '">comentarios públicos</a></p>';
    document.body.appendChild(f);
    var w = f.offsetWidth, h = f.offsetHeight;
    f.style.left = Math.max(16, Math.min(x + 12, innerWidth - w - 16)) + 'px';
    f.style.top = Math.max(16, Math.min(y + 12, innerHeight - h - 16)) + 'px';
    abierto = f;
    var ta = f.elements.texto, estado = f.querySelector('.estado');
    f.querySelector('[data-cerrar]').addEventListener('click', function () { cerrar(); if (antes && antes.focus) antes.focus(); });
    f.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); cerrar(); if (antes && antes.focus) antes.focus(); } });
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var texto = ta.value.trim();
      if (!texto) { ta.focus(); return; }
      if (/(https?:\/\/|www\.)/i.test(texto)) { estado.textContent = 'Sin enlaces, por favor: los robots viven de eso.'; return; }
      var boton = f.querySelector('button.si');
      boton.disabled = true;
      estado.textContent = 'un segundo… (un cálculo corto, para frenar a los robots)';
      var d = {
        texto: ta.value, firma: f.elements.firma.value,
        publico: f.elements.publico.checked, matriz: f.elements.matriz.checked,
        p: location.pathname, ts: Date.now(), web: f.elements.web.value
      };
      calcular(d).then(function (n) {
        d.n = n;
        return fetch(new URL('api/comentario', location.origin).href, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { r: r, j: j }; });
      }).then(function (x) {
        if (x.r.ok) {
          f.querySelector('.fila').innerHTML = '<button type="button" data-cerrar>cerrar</button>';
          f.querySelector('[data-cerrar]').addEventListener('click', cerrar);
          f.querySelector('[data-cerrar]').focus();
          ta.disabled = true;
          estado.textContent = x.j.estado === 'pendiente' ? 'Enviado. Queda para que la autora lo lea; si lo aprueba, se publica.' : 'Enviado. Lo lee solo la autora.';
          return;
        }
        boton.disabled = false;
        var e2 = x.j.error;
        estado.textContent = e2 === 'enlaces' ? 'Sin enlaces, por favor.' : e2 === 'largo' ? 'Es demasiado largo (hasta 1500 letras; la firma, 60).' :
          e2 === 'muchos' ? 'Llegaron muchos comentarios de tu zona en esta hora. Probá más tarde.' : e2 === 'repetido' ? 'Ese comentario ya llegó.' : 'No se pudo enviar (' + x.r.status + '). Probá de nuevo.';
      }).catch(function () {
        boton.disabled = false;
        estado.textContent = /^(localhost|127\.0\.0\.1)$/.test(location.hostname) || location.protocol === 'file:' ? 'Los comentarios solo se envían desde el sitio en línea.' : 'No se pudo enviar. Probá de nuevo.';
      });
    });
    setTimeout(function () { ta.focus(); }, 0);
  }

  function cerrar() { if (abierto) { abierto.remove(); abierto = null; } }
  document.addEventListener('pointerdown', function (e) { if (abierto && !abierto.contains(e.target) && !abierto.querySelector('textarea').value.trim()) cerrar(); });

  // prueba de trabajo: un número n tal que SHA-256(sobre) empiece con BITS ceros
  function calcular(d) {
    var enc = new TextEncoder();
    var pre = [d.ts, d.p, d.texto, d.firma || '', d.publico ? 1 : 0].join('|') + '|';
    function ok(buf) {
      var b = new Uint8Array(buf), bits = BITS, i = 0;
      while (bits >= 8) { if (b[i++] !== 0) return false; bits -= 8; }
      return bits === 0 || (b[i] >> (8 - bits)) === 0;
    }
    function tanda(desde) {
      var ps = [];
      for (var k = 0; k < 512; k++) ps.push(crypto.subtle.digest('SHA-256', enc.encode(pre + (desde + k))));
      return Promise.all(ps).then(function (hs) {
        for (var k = 0; k < hs.length; k++) if (ok(hs[k])) return desde + k;
        return tanda(desde + 512);
      });
    }
    return tanda(0);
  }
})();
