/* mareas.js — textos que solo aparecen en ciertos horarios, días o fechas.

   Las reglas están en mareas.json (las escribe la autora, a mano o desde el
   taller). Se evalúan con la hora de Argentina (UTC−3), la misma para
   todos: como una story, el texto está mientras dura su marea. Fuera de
   ella, en el índice se ve pero inhabilitado, y su página queda velada,
   con cuándo vuelve. Si la marea sube o baja mientras alguien lee, la página
   se abre o se vela sola.

   Una regla (todas las partes son opcionales; si hay varias, valen todas
   juntas, y dentro de cada lista alcanza con una):
     "horas":  ["20:00-06:00", "12:00-12:30"]   rangos (pueden cruzar la medianoche)
     "dias":   ["sab", "dom"]                   lun mar mie jue vie sab dom
     "fechas": ["2026-12-24", "11-02"]          exacta, o mes-día (todos los años)
     "desde":  "2026-10-01",  "hasta": "2026-11-01"   (hasta: inclusive)
     "mensaje": "texto propio para el velo (opcional)"
     "vuelve": "2026-10-10T18:00"               cooldown: hasta ese momento
                                                (hora de Argentina) el texto se
                                                va con la marea: sale del índice
                                                (queda al fondo, inundado) y su
                                                página se vela; después vuelve
                                                solo. Lo pone el botón «marea»
                                                del índice (solo la autora).

   Uso:
     MAREAS.cargar(base)            → promesa de { slug: regla }
     MAREAS.estado(regla, ahora?)   → { abierto, vuelve: Date|null, cierra: Date|null }
     MAREAS.velar(slug, base)       → vela la página si corresponde
     MAREAS.fuera(regla, ahora?)    → true si está en cooldown («vuelve» en el futuro)
     MAREAS.vuelveDe(regla)         → Date del fin del cooldown, o null */
(function () {
  'use strict';
  const DIAS = ['dom', 'lun', 'mar', 'mie', 'jue', 'vie', 'sab'];
  const sinTilde = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').slice(0, 3);
  const dos = n => String(n).padStart(2, '0');
  // Hora de Argentina (UTC−3, sin horario de verano): se corre el instante
  // 3 horas y se leen sus campos UTC.
  const AR = d => new Date(d.getTime() - 3 * 3600 * 1000);
  const fecha = d => { const a = AR(d); return a.getUTCFullYear() + '-' + dos(a.getUTCMonth() + 1) + '-' + dos(a.getUTCDate()); };
  const min = hhmm => { const m = /^(\d{1,2}):?(\d{2})?$/.exec(String(hhmm).trim()); return m ? (+m[1]) * 60 + (+(m[2] || 0)) : null; };

  // «vuelve»: fecha y hora de Argentina → instante
  const vuelveDe = r => {
    if (!r || !r.vuelve) return null;
    const m = /^(\d{4}-\d{2}-\d{2})(?:[T ](\d{1,2}):(\d{2}))?$/.exec(String(r.vuelve).trim());
    if (!m) return null;
    const d = new Date(m[1] + 'T' + dos(m[2] || 0) + ':' + (m[3] || '00') + ':00-03:00');
    return isNaN(d) ? null : d;
  };
  const fuera = (r, d) => { const v = vuelveDe(r); return !!v && (d || new Date()) < v; };

  let cache = null;
  function cargar(base) {
    if (!cache) cache = fetch((base || '') + 'mareas.json', { cache: 'no-cache' })
      .then(r => r.ok ? r.json() : {}).then(d => (d && d.textos) || {}).catch(() => ({}));
    return cache;
  }

  function abiertoEn(r, d) {
    if (!r) return true;
    if (fuera(r, d)) return false;
    const f = fecha(d);
    if (r.desde && f < r.desde) return false;
    if (r.hasta && f > r.hasta) return false;
    if (r.dias && r.dias.length && !r.dias.map(sinTilde).includes(DIAS[AR(d).getUTCDay()])) return false;
    if (r.fechas && r.fechas.length && !r.fechas.some(x => x === f || x === f.slice(5))) return false;
    if (r.horas && r.horas.length) {
      const m = AR(d).getUTCHours() * 60 + AR(d).getUTCMinutes();
      const dentro = r.horas.some(h => {
        const [a, b] = String(h).split('-').map(min);
        if (a == null || b == null) return false;
        return a <= b ? (m >= a && m < b) : (m >= a || m < b);
      });
      if (!dentro) return false;
    }
    return true;
  }
  // El próximo cambio, buscando de a 5 minutos hasta un año y medio.
  function proximo(r, desde, abierto) {
    // de minuto en minuto las primeras 24 h (las mareas pueden ser cortas),
    // después de a 5 minutos hasta un año y medio
    const d = new Date(desde); d.setSeconds(0, 0);
    for (let i = 0; i < 160000; i++) {
      d.setTime(d.getTime() + (i < 1440 ? 1 : 5) * 60000);
      if (abiertoEn(r, d) !== abierto) return new Date(d);
    }
    return null;
  }
  function estado(r, ahora) {
    ahora = ahora || new Date();
    if (fuera(r, ahora)) {
      // en cooldown: vuelve cuando termina (o, si además tiene horario, en
      // la primera marea alta después)
      const fin = vuelveDe(r), otras = Object.assign({}, r); delete otras.vuelve;
      return { abierto: false, fuera: true, vuelve: abiertoEn(otras, fin) ? fin : proximo(otras, fin, false), cierra: null };
    }
    const abierto = abiertoEn(r, ahora);
    const cambio = r ? proximo(r, ahora, abierto) : null;
    return { abierto, vuelve: abierto ? null : cambio, cierra: abierto ? cambio : null };
  }
  function cuando(d) {
    if (!d) return 'no tiene fecha de regreso';
    const hoy = new Date(), man = new Date(hoy.getTime() + 86400000);
    const a = AR(d), hora = dos(a.getUTCHours()) + ':' + dos(a.getUTCMinutes());
    if (fecha(d) === fecha(hoy)) return 'vuelve hoy a las ' + hora + ' (hora de Argentina)';
    if (fecha(d) === fecha(man)) return 'vuelve mañana a las ' + hora + ' (hora de Argentina)';
    return 'vuelve el ' + d.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Argentina/Buenos_Aires' }) + ' a las ' + hora + ' (hora de Argentina)';
  }

  function velar(slug, base) {
    return cargar(base).then(reglas => {
      const r = reglas[slug];
      if (!r) return;
      // la autora (con su token) lee siempre: el velo es para el público
      if (window.P314B && window.P314B.autor) return;
      const css = document.createElement('style');
      css.textContent = '.marea-velo{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;'
        + 'background:var(--page,#111);color:var(--ink-soft,#bbb);font-family:var(--font-mono,monospace);text-align:center;padding:24px;}'
        + '.marea-velo p{max-width:34em;line-height:1.7;margin:.4em 0}.marea-velo .mv-ola{font-size:28px;letter-spacing:.3em;opacity:.6;animation:mvola 6s ease-in-out infinite}'
        + '.marea-velo a{color:inherit}@keyframes mvola{50%{transform:translateY(6px);opacity:.3}}'
        + '@media (prefers-reduced-motion:reduce){.marea-velo .mv-ola{animation:none}}';
      document.head.appendChild(css);
      let velo = null;
      const mirar = () => {
        const e = estado(r);
        if (!e.abierto && !velo) {
          velo = document.createElement('div');
          velo.className = 'marea-velo';
          velo.setAttribute('role', 'dialog');
          document.body.appendChild(velo);
          document.documentElement.style.overflow = 'hidden';
        }
        if (!e.abierto) {
          velo.innerHTML = '<div><div class="mv-ola">∿∿∿</div><p>' + (e.fuera ? 'Este texto se fue con la marea.' : 'Este texto está en marea baja.') + '</p>'
            + (r.mensaje ? '<p>' + String(r.mensaje).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c])) + '</p>' : '')
            + '<p>' + cuando(e.vuelve) + '.</p><p><a href="' + (base || '') + 'index.html">volver al índice</a></p></div>';
        } else if (velo) {
          velo.remove(); velo = null;
          document.documentElement.style.overflow = '';
        }
      };
      mirar();
      const t = setInterval(mirar, 30000);
      if (window.P314B && window.P314B.listo) window.P314B.listo.then(ok => {
        if (!ok) return;
        clearInterval(t);
        if (velo) { velo.remove(); velo = null; document.documentElement.style.overflow = ''; }
      });
    });
  }

  window.MAREAS = { cargar, estado, velar, cuando, fuera, vuelveDe, abierto: (r, d) => abiertoEn(r, d || new Date()) };
})();
