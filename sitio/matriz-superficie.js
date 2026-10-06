/* matriz-superficie.js — la superficie relacional.
 *
 * Lee un texto nuevo (lo que la autora escribe o sube en el taller) contra
 * todo el cuerpo, con el índice que arma a mano
 * matriz/anexo/scripts/superficie.py (sitio/matriz/superficie/). Nada se
 * calcula en la plataforma: el índice está fijo en archivos y el análisis
 * corre en el navegador.
 *
 * Qué devuelve para un texto:
 *   - atractor: el núcleo (fase 2) hacia el que gravita y el régimen de
 *     contexto (fase 5) más cercano
 *   - trayectoria: dónde cae en las dos firmas de +0 (fase 4)
 *   - operadores: las funciones de relación que usa (negación, mismidad,
 *     modalidad, al-menos-dos…) contra su línea de base en cada período
 *   - espacio de los 60 nodos convergentes (fase 5): cuáles activa y en qué
 *     sentido de período los usa
 *   - pasajes asociados de todo el cuerpo, inmediatos o de hace años, con
 *     el criterio de asociación, los nodos de mediación y el tipo de
 *     relacionalidad; ordenables por afinidad, por lo no obvio o por tiempo
 *
 * La lematización es la de matriz/anexo/scripts/lematica.py (que sigue a
 * diagonal.js + lemas.json): las listas de palabras vacías vienen del
 * propio índice para que las claves coincidan.
 *
 * Uso: await Superficie.cargar(); const r = Superficie.analizar(texto, {excluirObra});
 *      Superficie.pintar(elemento, r, {texto});
 */
(function () {
  'use strict';
  const RUTA = 'matriz/superficie/';
  let LEX = null, PAS = null, PERF = null, LEM = null, KID = null, prom = null;
  let AUTO = new Map(), LEMAS_AUTO = new Set();
  let FAM = new Map();   // obra → sus otras versiones (el mismo texto en otro archivo)
  let RECON = new Map(), DEL_TALLER = new Map(), F = Object.create(null), LEMAS_DEF = new Set(), IGN = new Set(), VACIAS = new Set(), EXTRA = new Set();

  const norm = w => w.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  const esc = P314.esc;
  const HOY = (() => { const d = new Date(); return d.getFullYear() + (d - new Date(d.getFullYear(), 0, 1)) / 31557600000; })();

  async function leer(ruta, texto) {
    const r = await fetch(ruta, { cache: 'no-store' });
    if (!r.ok) throw new Error(ruta + ': HTTP ' + r.status);
    return texto ? r.text() : r.json();
  }

  async function cargar() {
    if (prom) return prom;
    prom = (async () => {
      let A, REL;
      [LEX, PAS, PERF, LEM, A, REL] = await Promise.all([leer(RUTA + 'lexico.json'), leer(RUTA + 'pasajes.json'), leer(RUTA + 'perfil.json'),
        leer('lemas.json').catch(() => ({})), leer('lemas-auto.json').catch(() => ({})), leer('matriz/relaciones.json').catch(() => ({}))]);
      prepararLemas(LEM, A);
      KID = new Map(LEX.claves.map((c, i) => [c, i]));
      VACIAS = new Set(PERF.lematizacion.vacias); EXTRA = new Set(PERF.lematizacion.extra);
      LEX.lir = new Set(LEX.lirico);
      // id de cada obra en el taller → su clave en el índice (los PDF pueden diferir)
      DEL_TALLER = new Map(Object.entries(PERF.obras).filter(([, o]) => o.taller).map(([k, o]) => [o.taller, k]));
      // versiones del mismo texto (lectura del Cowork, relaciones.json): leer
      // una obra contra su otra versión devuelve el mismo texto como «asociado»
      FAM = new Map();
      const clv = x => { const t = String(x).replace(/^sitio:/, ''); return DEL_TALLER.get(t) || t; };
      (REL.versiones || []).filter(v => v.compartido >= 0.5).forEach(v => {
        const a = clv(v.a), b = clv(v.b);
        if (a === b) return;
        (FAM.get(a) || FAM.set(a, new Set()).get(a)).add(b);
        (FAM.get(b) || FAM.set(b, new Set()).get(b)).add(a);
      });
      // lo que la autora ya relaciona por uso: claves de sus diagonales tendidas
      RECON = new Map();
      (PERF.reconocidas || []).forEach(d => d.claves.forEach(c => { const i = KID.get(c); if (i != null && !RECON.has(i)) RECON.set(i, d.titulo); }));
      return true;
    })();
    prom.catch(() => { prom = null; });
    return prom;
  }

  /* ── lematización (idéntica a lematica.py; tests/test_lematizacion.py lo comprueba) ── */
  function prepararLemas(L, A) {
    // sin prototipo: «constructor» o «tostring» en un texto no son lemas
    F = Object.create(null); Object.entries(L.formas || {}).forEach(([k, v]) => { F[k.toLowerCase()] = v; });
    LEMAS_DEF = new Set(Object.values(F).map(v => v.toLowerCase()));
    IGN = new Set(L.ignorar || []);
    AUTO = new Map((A.propias || []).map(w => [w, w]));
    Object.entries(A.formas || {}).forEach(([k, v]) => AUTO.set(k, v));
    LEMAS_AUTO = new Set([...AUTO.values()].map(norm));
  }
  const IRREG = { es: 'ser', son: 'ser', era: 'ser', eran: 'ser', fue: 'ser', fueron: 'ser', sea: 'ser', sean: 'ser', siendo: 'ser', sido: 'ser', sera: 'ser', soy: 'ser', somos: 'ser', seria: 'ser',
    esta: 'estar', estan: 'estar', estaba: 'estar', estando: 'estar', estamos: 'estar',
    tiene: 'tener', tienen: 'tener', tenia: 'tener', tenga: 'tener', tuvo: 'tener',
    hace: 'hacer', hacen: 'hacer', hizo: 'hacer', hecho: 'hacer', haciendo: 'hacer',
    dice: 'decir', dicen: 'decir', dijo: 'decir', diciendo: 'decir', decimos: 'decir', diriamos: 'decir', deciamos: 'decir',
    puede: 'poder', pueden: 'poder', podia: 'poder', pudo: 'poder', podemos: 'poder', podria: 'poder', podriamos: 'poder' };
  const REGLAS = [[/ciones$/, 'cion'], [/siones$/, 'sion'], [/idades$/, 'idad'], [/ces$/, 'z'],
    [/iendo$/, 'er'], [/ando$/, 'ar'], [/(ados|adas|ado|ada)$/, 'ar'], [/(idos|idas|ido|ida)$/, 'er'],
    [/(abamos|aban|abas|aba)$/, 'ar'], [/(iamos|ian)$/, 'er'], [/(aron|amos)$/, 'ar'], [/(ieron|emos|imos)$/, 'er'],
    [/ones$/, 'on'], [/([^aeiou])es$/, '$1'], [/([aeiou])s$/, '$1']];
  function lema(w) {
    const bajo = w.toLowerCase();
    if (bajo === 'sí') return 'sí';
    const dado = F[bajo] || F[norm(bajo)];
    if (dado) return dado === 'sí' ? 'sí' : norm(dado);
    let n = norm(w);
    if (Object.hasOwn(IRREG, n)) return IRREG[n];
    const auto = AUTO.get(bajo);
    if (auto) return norm(F[auto] || F[norm(auto)] || auto);
    if (n.length > 7) n = n.replace(/mente$/, '');
    for (const [rx, rep] of REGLAS) if (rx.test(n)) { n = n.replace(rx, rep); break; }
    return n;
  }
  function clave(w) {
    const l = lema(w), bajo = w.toLowerCase();
    let c;
    if (l === 'sí' || F[bajo] || F[norm(w)]) c = l;
    else if (LEMAS_DEF.has(bajo)) c = bajo;
    else if (AUTO.has(bajo) || LEMAS_AUTO.has(l)) c = l;
    else { const r = l.replace(/(ar|er|ir)$/, ''); c = r.length >= 4 ? r : l; }
    return c === 'sí' ? 'sí' : norm(c);
  }
  function cuenta(w) {
    if (w.toLowerCase() === 'sí') return true;
    const n = norm(w);
    return w.length >= 3 && !VACIAS.has(n) && !EXTRA.has(n) && !IGN.has(w);
  }
  const TOKEN = /[\p{L}\p{M}][\p{L}\p{M}]+/gu;  // como lematica.py: solo letras, sin guiones
  function tokens(txt) {
    const out = []; let m; TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(txt))) if (cuenta(m[0])) out.push({ forma: m[0], c: clave(m[0]), i: m.index });
    return out;
  }

  /* ── la firma formal (criterios_base.medir_ventana, cq, costo…) ── */
  const FUN = new Set('que de la el en y a los se no ni lo las un una por con su del al es o como más mas pero si sin para ya le me te nos tu mi'.split(' '));
  const VOC = 'aeiou';
  function rima(w) {
    w = norm(w); const idx = [...w].map((c, i) => VOC.includes(c) ? i : -1).filter(i => i >= 0);
    if (!idx.length) return null;
    const i = idx.length >= 2 && (VOC + 'ns').includes(w[w.length - 1]) ? idx[idx.length - 2] : idx[idx.length - 1];
    return [...w.slice(i)].filter(c => VOC.includes(c)).join('');
  }
  function medir(t, claves) {
    const toks = (t.match(/[\p{L}]+/gu) || []).map(w => w.toLowerCase());
    const T = toks.length;
    if (T < 200) return null;
    const V = new Set(toks).size;
    const L = ['<s>', ...toks.slice(0, -1)], R = [...toks.slice(1), '</s>'];
    const inst = new Set(toks.map((w, i) => (FUN.has(L[i]) ? L[i] : '*') + '|' + w + '|' + (FUN.has(R[i]) ? R[i] : '*')));
    const marcas = new Set(); let m; const rp = /[^\w\s]+/gu;
    while ((m = rp.exec(t))) { const a = t[m.index - 1] || ' ', b = t[m.index + m[0].length] || ' '; marcas.add(m[0] + (/\s/.test(a) ? 1 : 0) + (/\s/.test(b) ? 1 : 0)); }
    const Vg = marcas.size + (/\n\s*\n/.test(t) ? 1 : 0) + (/[^\n]\n[^\n]/.test(t) ? 1 : 0) + (/\S {3,}\S/.test(t) ? 1 : 0);
    const fin = []; const rf = /([\p{L}]+)\s*(?:[.,;:!?¡¿…–—-]|\n)/gu; while ((m = rf.exec(t))) fin.push(m[1]);
    const Vf = new Set(fin.map(rima).filter(Boolean)).size;
    const cc = {}; claves.forEach(c => { cc[c] = (cc[c] || 0) + 1; });
    const Vc = Object.values(cc).filter(n => n >= 3).length;
    let rep = 0; toks.forEach((w, i) => { if (toks.slice(Math.max(0, i - 2), i).includes(w)) rep++; });
    const cortes = (t.match(/[^\w\s]+/gu) || []).length + (t.match(/[^\n]\n(?!\n)/g) || []).length + (t.match(/\n\s*\n/g) || []).length + (t.match(/\S {3,}\S/g) || []).length;
    const est = new Set(PERF.firma.ESTANDAR);
    const costo = claves.filter(c => !est.has(c)).length / Math.max(1, claves.length);
    const hiper = claves.filter(c => !KID.has(c) && !Object.hasOwn(LEX.raras, c)).length / Math.max(1, claves.length);
    const pl = (t.match(/\b(nosotros|nosotras|nuestro|nuestra|nuestros|nuestras|nos)\b/giu) || []).length;
    const sg = (t.match(/(?<![\p{L}])(yo|me|mí|mi|mis|conmigo|mío|mía|míos|mías)(?![\p{L}])/giu) || []).length;
    return { T, cq: cortes / Math.max(1, T - 1), IIN: inst.size * inst.size / ((Vc + Vg + Vf) * T), Esint: Vc / T, Eg: Vg / T,
      costo, hiper, dos: (Math.min(pl, sg) + 1) / (Math.max(pl, sg) + 1), TTR: V / T, DRI: rep / T };
  }

  /* ── análisis ── */
  function analizar(texto, op = {}) {
    if (!LEX) throw new Error('Superficie: primero cargar()');
    const tk = tokens(texto), claves = tk.map(x => x.c);
    const cnt = new Map(); claves.forEach(c => cnt.set(c, (cnt.get(c) || 0) + 1));
    // vector del texto (tf-idf) y su expansión estructural (mediación)
    const q = new Map(); let nq = 0;
    cnt.forEach((n, c) => { const i = KID.get(c); if (i == null) return; const w = (1 + Math.log(n)) * LEX.idf[i]; q.set(i, w); nq += w * w; });
    nq = Math.sqrt(nq) || 1; q.forEach((w, i) => q.set(i, w / nq));
    const med = new Map(), via = new Map();   // clave vecina → peso, y desde qué clave del texto
    q.forEach((w, i) => (LEX.vecinos[i] || []).forEach(v => {
      if (q.has(v)) return;
      const nw = 0.35 * w;
      if (nw > (med.get(v) || 0)) { med.set(v, nw); via.set(v, i); }
    }));
    // puntaje de cada pasaje (p.k = [clave, peso en centésimos, clave, peso…])
    // sin la obra misma ni sus otras versiones
    const fuera = new Set();
    if (op.excluirObra) {
      const k = DEL_TALLER.get(op.excluirObra) || op.excluirObra;
      fuera.add(k); (FAM.get(k) || []).forEach(x => fuera.add(x));
    }
    const res = [];
    for (let j = 0; j < PAS.length; j++) {
      const p = PAS[j];
      if (fuera.has(p.o)) continue;
      let d = 0, m = 0;
      const k = p.k;
      for (let n = 0; n < k.length; n += 2) { const i = k[n], w = k[n + 1] / 100, a = q.get(i); if (a) d += a * w; else { const b = med.get(i); if (b) m += b * w; } }
      if (d + m > 0.02) res.push([j, d, m]);
    }
    res.sort((a, b) => (b[1] + b[2]) - (a[1] + a[2]));
    const top = res.slice(0, 400).map(([j, d, m]) => describir(PAS[j], d, m, q, med, via));
    // atractor nodal: núcleos (fase 2)
    const nuc = PERF.nucleos.map((n, k) => ({ k, palabra: n.palabra, acunada: n.acunada, puntos: 0, por: new Set() }));
    q.forEach((w, i) => {
      const k = LEX.nucleo[i]; if (k != null) { nuc[k].puntos += w; nuc[k].por.add(LEX.forma[i]); }
      (LEX.vecinos[i] || []).forEach(v => { const kk = LEX.nucleo[v]; if (kk != null) { nuc[kk].puntos += 0.4 * w; nuc[kk].por.add(LEX.forma[i]); } });
    });
    // un núcleo grande (muchos miembros, algunos muy comunes: «nada»,
    // «saber») atraía casi cualquier texto: se pondera por su tamaño y hace
    // falta tocarlo por dos palabras distintas
    nuc.forEach(n => { n.puntos = n.por.size >= 2 ? n.puntos / Math.sqrt((PERF.nucleos[n.k].miembros || []).length || 1) : 0; });
    nuc.sort((a, b) => b.puntos - a.puntos);
    // régimen de contexto (fase 5): cercanía a cada atractor de período
    const regimen = Object.entries(PERF.atractores).map(([p, lista]) => {
      const set = new Set(lista.map(c => KID.get(c)).filter(i => i != null));
      let s = 0; q.forEach((w, i) => { if (set.has(i)) s += w; else if ((LEX.vecinos[i] || []).some(v => set.has(v))) s += 0.3 * w; });
      return { periodo: p, puntos: s };
    }).sort((a, b) => b.puntos - a.puntos);
    // espacio de los 60 nodos convergentes
    const nodos = [];
    PERF.convergentes.forEach(n => {  // (se ordenan por uso al final)
      const pos = []; claves.forEach((c, i) => { if (c === n.nodo) pos.push(i); });
      if (!pos.length) return;
      const ctx = new Set(); pos.forEach(i => claves.slice(Math.max(0, i - 8), i + 9).forEach(c => { if (c !== n.nodo) ctx.add(c); }));
      const sentido = Object.entries(n.vecinos).map(([p, vs]) => ({ p, n: vs.filter(v => ctx.has(norm(v))).length }))
        .sort((a, b) => b.n - a.n);
      nodos.push({ nodo: n.nodo, forma: n.forma, veces: pos.length, tipo: n.tipo, sentido: sentido[0].n ? sentido[0].p : null, vecinos: n.vecinos });
    });
    nodos.sort((a, b) => b.veces - a.veces);
    // operadores de relación
    const bajo = texto.toLowerCase(), nw = (texto.match(/[\p{L}]+/gu) || []).length || 1;
    const operadores = Object.entries(PERF.operadores).map(([nom, o]) => {
      const tasa = 1000 * (bajo.match(new RegExp(o.rx, 'gu')) || []).length / nw;
      const z = Object.fromEntries(Object.entries(o.base).map(([p, [mu, sd]]) => [p, (tasa - mu) / (sd || 1)]));
      return { nombre: nom, tasa, base: o.base, z };
    });
    const pers = Object.keys(PERF.operadores['negación'].base);
    const cercania = pers.map(p => ({ p, d: operadores.reduce((s, o) => s + Math.pow(o.z[p] || 0, 2), 0) })).sort((a, b) => a.d - b.d);
    // firma de +0 (fase 4)
    let firma = null;
    const f = medir(texto, claves);
    if (f) {
      const M = PERF.firma;
      const raw = M.K.reduce((s, k, i) => s + ((f[k] - M.mu[i]) / M.sd[i]) * M.w[i], 0);
      const lexraw = claves.reduce((s, c) => s + (Object.hasOwn(M.LEX, c) ? M.LEX[c] : 0), 0) / Math.max(1, claves.length);
      firma = { formal: (raw - M.s0) / (M.s1 - M.s0), lexica: (lexraw - M.l0) / (M.l1 - M.l0), medidas: f, por_carpeta: PERF.firma_por_carpeta };
    }
    return { palabras: nw, claves: claves.length, conocidas: q.size, tokens: tk, pasajes: top, nucleos: nuc.slice(0, 4).map(n => ({ ...n, por: [...n.por].slice(0, 8) })),
      regimen, nodos, operadores, cercaniaOperadores: cercania, firma };
  }

  function describir(p, d, m, q, med, via) {
    const comp = [], medi = [], nuc = new Set(), conv = [];
    for (let n = 0; n < p.k.length; n += 2) {
      const i = p.k[n];
      if (q.has(i)) { comp.push(i); if (LEX.nucleo[i] != null) nuc.add(LEX.nucleo[i]); if (LEX.convergente[i] != null) conv.push(i); }
      else if (med.has(i)) { medi.push([via.get(i), i]); if (LEX.nucleo[i] != null) nuc.add(LEX.nucleo[i]); }
    }
    const edad = p.f != null ? HOY - p.f : null;
    const tipos = [];
    if (d >= m && comp.length) tipos.push('resonancia léxica');
    if (medi.length) tipos.push('sustitución estructural');
    nuc.forEach(k => tipos.push('núcleo: ' + PERF.nucleos[k].palabra));
    if (conv.length) tipos.push('vector de convergencia');
    if (edad != null && edad >= 5) tipos.push('diagonal de largo alcance');
    // ¿la relación pasa por una diagonal que la autora ya tendió?
    const ya = [...new Set(comp.filter(i => RECON.has(i)).map(i => RECON.get(i)))];
    const soloYa = comp.length > 0 && comp.every(i => RECON.has(i)) && !medi.length;
    if (ya.length) tipos.push('ya en tu diagonal: ' + ya.join(', '));
    else tipos.push('relación no tendida');
    // lo raro pesa más que lo común: la parte no obvia de la afinidad
    const rareza = comp.reduce((s, i) => s + LEX.idf[i], 0) / Math.max(1, comp.length);
    const noObvio = m + d * Math.min(1, rareza / 8) * (comp.length <= 2 ? 1 : 0.6) + (edad != null ? Math.min(edad, 9) * 0.004 : 0);
    return { p, directo: d, mediado: m, total: d + m, comp, medi, nucleos: [...nuc], conv, edad, tipos, ya,
      noObvio: soloYa ? noObvio * 0.3 : ya.length ? noObvio * 0.7 : noObvio };
  }

  /* ── pintar el resultado ── */
  const NOMPER = { '2017-19': '2017-19', '2020-22': '2020-22', 'TyC': 'Términos y condiciones', '2023-25': '2023-25', '+0': 'VI - +0' };
  const fmt = (v, n) => v == null || isNaN(v) ? '—' : Number(v).toFixed(n).replace('.', ',');
  function edadTxt(e) { if (e == null) return 'sin fecha'; if (e < 1) return 'este año'; const a = Math.round(e); return 'hace ' + a + (a === 1 ? ' año' : ' años'); }

  function pintar(el, r, op = {}) {
    // por defecto, lo no obvio: por afinidad ganan siempre las mismas obras largas
    const estado = el._sup = { r, orden: 'noobvio', rango: 'todo', sel: null, texto: op.texto || '' };
    const obra = o => (PERF.obras[o] || {}).titulo || o;
    const nuc = r.nucleos.filter(n => n.puntos > 0);
    const reg = r.regimen[0];
    const f = r.firma;
    const opsDistintos = r.operadores.filter(o => Math.abs(o.z['+0'] ?? 0) > 1), opsComo = r.operadores.filter(o => Math.abs(o.z['+0'] ?? 0) <= 1);
    const barra = v => `<span class="sup-barra"><i style="left:${Math.max(0, Math.min(100, v * 100))}%"></i></span>`;
    el.innerHTML = `
      <div class="sup">
        <div class="sup-meta">${r.palabras} palabras · ${r.conocidas} claves del cuerpo${op.origen ? ' · ' + esc(op.origen) : ''}</div>
        <section><h4>concepto nodal atractor</h4>
          ${nuc.length ? nuc.slice(0, 3).map((n, i) => `<div class="sup-nuc${i ? ' sec' : ''}"><b>${esc(n.palabra)}</b> → <i>${esc(n.acunada)}</i><span>por ${esc(n.por.join(', '))}</span></div>`).join('') : '<p class="sup-nota">Todavía no gravita hacia ningún núcleo.</p>'}
          <p class="sup-nota">Régimen de contexto más cercano: <b>${esc(NOMPER[reg.periodo])}</b>${r.regimen[1] ? `, después ${esc(NOMPER[r.regimen[1].periodo])}` : ''}.</p>
        </section>
        <section><h4>trayectoria · firma de +0</h4>
          ${f ? `<div class="sup-firma"><span>formal</span>${barra(f.formal)}<em>${fmt(f.formal, 2)}</em></div>
                 <div class="sup-firma"><span>léxica</span>${barra(f.lexica)}<em>${fmt(f.lexica, 2)}</em></div>
                 <p class="sup-nota">0 es I - Estudio 2017-19; 1 es +0. Por carpeta (formal): ${Object.entries(f.por_carpeta.formal).map(([c, v]) => esc(c.split(' - ')[0].replace('en curso (sin carpeta)', 'en curso')) + ' ' + fmt(v, 2)).join(' · ')}.</p>`
             : '<p class="sup-nota">Hace falta un texto de al menos 200 palabras para ubicarlo en la trayectoria.</p>'}
        </section>
        <section><h4>operadores de relación</h4>
          ${opsDistintos.length ? `<table class="sup-ops"><tbody>${opsDistintos.map(o => { const z = o.z['+0']; return `<tr><td>${esc(o.nombre)}</td><td>${fmt(o.tasa, 1)}</td><td><span class="sup-z ${z > 1 ? 'mas' : 'menos'}">${z > 1 ? 'más que en +0' : 'menos que en +0'}</span></td></tr>`; }).join('')}</tbody></table>` : ''}
          <p class="sup-nota">${opsDistintos.length ? 'Solo los que se apartan de +0, por 1000 palabras. ' : ''}${opsComo.length ? (opsDistintos.length ? 'Como en +0: ' : 'Relaciona como +0 en todos: ') + esc(opsComo.map(o => o.nombre).join(', ')) + '. ' : ''}${r.palabras < 150 ? 'Con menos de 150 palabras las tasas son inestables.' : `Por cómo relaciona, tu texto se parece más a <b>${esc(NOMPER[r.cercaniaOperadores[0].p])}</b>.`}</p>
        </section>
        <section><h4>espacio de los 60 nodos</h4>
          ${r.nodos.length ? `<div class="sup-nodos">${r.nodos.map(n => `<span class="sup-nodo" title="${esc(n.tipo)} · vecinos en ${esc(NOMPER[n.sentido] || '—')}: ${esc((n.vecinos[n.sentido] || []).join(', '))}">${esc(n.forma)}${n.veces > 1 ? ' ×' + n.veces : ''}<small>${esc(n.sentido ? NOMPER[n.sentido] : 'sentido propio')}</small></span>`).join('')}</div>
            <p class="sup-nota">Nodos convergentes que el texto activa y en qué sentido de período los usa (por su vecindario).</p>` : '<p class="sup-nota">No activa ninguno de los 60.</p>'}
        </section>
        <section><h4>pasajes asociados</h4>
          <div class="sup-ctrl">
            <label>ordenar <select data-sup="orden"><option value="noobvio">lo no obvio primero</option><option value="afinidad">por afinidad</option><option value="nueva">solo relaciones no tendidas</option><option value="lejos">lo más lejano primero</option><option value="cerca">lo más reciente primero</option></select></label>
            <label>tiempo <select data-sup="rango"><option value="todo">todo el cuerpo</option><option value="reciente">últimos 2 años</option><option value="lejos">hace 5 años o más</option></select></label>
          </div>
          <div class="sup-lista"></div>
        </section>
        ${estado.texto ? `<section><h4>tu texto, resaltado</h4><div class="sup-texto"></div><p class="sup-nota"><span class="sup-h conv">nodo convergente</span> <span class="sup-h nuc">de un núcleo</span> <span class="sup-h sel">compartido con el pasaje elegido</span></p></section>` : ''}
      </div>`;
    el.querySelector('[data-sup="orden"]').addEventListener('change', e => { estado.orden = e.target.value; lista(el); });
    el.querySelector('[data-sup="rango"]').addEventListener('change', e => { estado.rango = e.target.value; lista(el); });
    lista(el); resaltar(el);
  }

  function lista(el) {
    const st = el._sup, r = st.r;
    let ps = r.pasajes.filter(x => st.rango === 'todo' || (x.edad != null && (st.rango === 'reciente' ? x.edad <= 2 : x.edad >= 5)));
    if (st.orden === 'nueva') ps = ps.filter(x => !x.ya.length);
    const ord = { afinidad: (a, b) => b.total - a.total, nueva: (a, b) => b.noObvio - a.noObvio, noobvio: (a, b) => b.noObvio - a.noObvio,
      lejos: (a, b) => (b.edad || 0) - (a.edad || 0) || b.total - a.total, cerca: (a, b) => (a.edad ?? 99) - (b.edad ?? 99) || b.total - a.total }[st.orden];
    // a lo sumo dos pasajes por obra: si no, una obra larga llena la lista
    const porObra = {}, apartados = {};
    ps = ps.slice(0, 120).sort(ord).filter(x => {
      porObra[x.p.o] = (porObra[x.p.o] || 0) + 1;
      if (porObra[x.p.o] <= 2) return true;
      apartados[x.p.o] = (apartados[x.p.o] || 0) + 1; return false;
    }).slice(0, 14);
    const obra = o => (PERF.obras[o] || {}).titulo || o;
    const cont = el.querySelector('.sup-lista');
    if (!ps.length) { cont.innerHTML = '<p class="sup-nota">Nada en este rango.</p>'; return; }
    // lo que comparten casi todos no distingue a ninguno: va una vez, arriba
    const general = t => t.replace(/:.*/, '');
    const frec = {}; ps.forEach(x => new Set(x.tipos.map(general)).forEach(t => { frec[t] = (frec[t] || 0) + 1; }));
    const comunes = new Set(Object.keys(frec).filter(t => ps.length >= 4 && frec[t] >= 0.8 * ps.length && !t.startsWith('ya en')));
    const masDe = Object.entries(apartados).sort((a, b) => b[1] - a[1]).slice(0, 3);
    cont.innerHTML = (comunes.size ? `<p class="sup-nota">Casi todos: ${esc([...comunes].join(' · '))}.</p>` : '')
      + (masDe.length ? `<p class="sup-nota">Hay más en ${masDe.map(([o, n]) => esc(obra(o)) + ' (' + n + ')').join(', ')}: se muestran dos por obra.</p>` : '')
      + ps.map((x, n) => {
      const pal = x.comp.slice(0, 8).map(i => LEX.forma[i]);
      const medTxt = x.medi.slice(0, 4).map(([a, b]) => `${esc(LEX.forma[a])} → ${esc(LEX.forma[b])}`).join(' · ');
      let frag = esc(x.p.t);
      pal.forEach(w => { frag = frag.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'giu'), '<mark>$1</mark>'); });
      const lugar = x.p.pg != null ? 'p. ' + x.p.pg : 'capítulo';
      return `<article class="sup-pas" data-n="${n}">
        <header><b>${esc(obra(x.p.o))}</b> · ${lugar} · <span class="sup-edad">${edadTxt(x.edad)}${x.p.f ? ' (' + Math.floor(x.p.f) + ')' : ''}</span><em>${fmt(x.total, 2)}</em></header>
        <p class="sup-frag">${frag}…</p>
        <div class="sup-tipos">${x.tipos.filter(t => !comunes.has(general(t))).map(t => `<span class="${t.startsWith('ya en') ? 'ya' : t === 'relación no tendida' ? 'nueva' : ''}">${esc(t)}</span>`).join('')}</div>
        <dl>${pal.length ? `<dt>criterio</dt><dd>comparte ${esc(pal.join(', '))}</dd>` : ''}
            ${medTxt ? `<dt>mediación</dt><dd>${medTxt}</dd>` : ''}</dl>
        <div class="sup-acc"><button data-ver="${n}">ver pasaje completo</button>${(PERF.obras[x.p.o] || {}).publicado ? `<a href="obras/${encodeURIComponent(PERF.obras[x.p.o].html)}" target="_blank" rel="noopener">abrir la obra</a>` : ''}</div>
        <div class="sup-completo" hidden></div>
      </article>`;
    }).join('');
    cont.querySelectorAll('.sup-pas').forEach(a => a.addEventListener('click', e => {
      if (e.target.closest('a,button')) return;
      st.sel = ps[+a.dataset.n]; cont.querySelectorAll('.sup-pas').forEach(b => b.classList.toggle('on', b === a)); resaltar(el);
    }));
    cont.querySelectorAll('[data-ver]').forEach(b => b.addEventListener('click', async () => {
      const x = ps[+b.dataset.ver], box = b.closest('.sup-pas').querySelector('.sup-completo');
      if (!box.hidden) { box.hidden = true; return; }
      box.hidden = false; box.textContent = 'cargando…';
      try { box.textContent = await completo(x.p); } catch (e) { box.textContent = 'No se pudo leer el pasaje completo (' + e.message + ').'; }
    }));
  }

  async function completo(p) {
    const o = PERF.obras[p.o] || {};
    if (p.pg != null && o.archivo) {
      const t = await leer('Archivo/' + o.archivo.replace(/\.pdf$/i, '.txt'), true);
      const partes = t.split(/<<<PAGE (\d+)>>>/);
      for (let i = 1; i < partes.length; i += 2) if (+partes[i] === +p.pg) return partes[i + 1].trim();
      return p.t;
    }
    const d = await leer('obras/' + (o.taller || p.o) + '.json');
    const ch = (d.chapters || []).find(c => c.id === p.cap);
    const div = document.createElement('div'); div.innerHTML = (ch && ch.body) || '';
    return (div.textContent || p.t).trim();
  }

  function resaltar(el) {
    const st = el._sup, box = el.querySelector('.sup-texto');
    if (!box) return;
    const conv = new Set(st.r.nodos.map(n => n.nodo));
    const selC = new Set(st.sel ? [...st.sel.comp.map(i => LEX.claves[i]), ...st.sel.medi.map(([a]) => LEX.claves[a])] : []);
    const t = st.texto; let h = '', pos = 0;
    st.r.tokens.forEach(k => {
      const i = KID.get(k.c);
      const cls = selC.has(k.c) ? 'sel' : conv.has(k.c) ? 'conv' : (i != null && LEX.nucleo[i] != null) ? 'nuc' : '';
      if (!cls) return;
      h += esc(t.slice(pos, k.i)) + `<span class="sup-h ${cls}">${esc(k.forma)}</span>`; pos = k.i + k.forma.length;
    });
    h += esc(t.slice(pos));
    box.innerHTML = h.replace(/\n/g, '<br>');
  }

  // estilos del panel (una vez)
  function estilos() {
    if (document.getElementById('sup-css')) return;
    const s = document.createElement('style'); s.id = 'sup-css';
    s.textContent = `
.sup{display:flex;flex-direction:column;gap:18px;font-family:var(--font-body,Georgia,serif);color:var(--ink,#f5f5f5)}
.sup section{display:flex;flex-direction:column;gap:6px}
.sup h4{font:500 10px/1.4 var(--font-mono,monospace);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-muted,#9a9a9a);margin:0}
.sup-meta,.sup-nota{font-size:13px;color:var(--ink-muted,#9a9a9a);margin:0;line-height:1.5}
.sup-nota b{color:var(--ink-soft,#d0d0d0);font-weight:500}
.sup-nuc{font-size:18px}.sup-nuc.sec{font-size:15px;color:var(--ink-soft,#d0d0d0)}
.sup-nuc i{color:var(--mark-lt,#60a5fa)}.sup-nuc span{display:block;font-size:12px;color:var(--ink-muted,#9a9a9a)}
.sup-firma{display:grid;grid-template-columns:56px 1fr 44px;gap:8px;align-items:center;font:12px var(--font-mono,monospace);color:var(--ink-soft,#d0d0d0)}
.sup-barra{position:relative;height:6px;background:linear-gradient(90deg,#1b2a4a,#3b82f6,#eab308);border-radius:3px}
.sup-barra i{position:absolute;top:-4px;width:3px;height:14px;background:#f5f5f5;transform:translateX(-1px)}
.sup-firma em{font-style:normal;text-align:right}
.sup-ops{border-collapse:collapse;font-size:13px;width:100%}.sup-ops td{padding:3px 4px;border-bottom:1px solid var(--rule,#292929)}
.sup-ops td:nth-child(2){font-family:var(--font-mono,monospace);text-align:right;color:var(--ink-soft,#d0d0d0)}
.sup-z{font:11px var(--font-mono,monospace);color:var(--ink-muted,#9a9a9a)}.sup-z.mas{color:#eab308}.sup-z.menos{color:var(--mark-lt,#60a5fa)}
.sup-nodos{display:flex;flex-wrap:wrap;gap:6px}
.sup-nodo{border:1px solid var(--rule,#292929);border-radius:3px;padding:2px 7px;font-size:14px;background:var(--bg-alt,#111)}
.sup-nodo small{display:block;font:10px var(--font-mono,monospace);color:#eab308}
.sup-ctrl{display:flex;gap:10px;flex-wrap:wrap;font:11px var(--font-mono,monospace);color:var(--ink-muted,#9a9a9a)}
.sup-ctrl select{background:var(--bg-alt,#111);color:var(--ink,#f5f5f5);border:1px solid var(--rule,#292929);font:inherit;padding:2px 4px}
.sup-lista{display:flex;flex-direction:column;gap:10px}
.sup-pas{border:1px solid var(--rule,#292929);border-radius:3px;padding:10px 12px;background:var(--page,#0d0d0d);cursor:pointer}
.sup-pas.on{border-color:var(--mark,#3b82f6);background:var(--mark-bg,rgba(59,130,246,.1))}
.sup-pas header{font-size:13px;color:var(--ink-soft,#d0d0d0);display:flex;flex-wrap:wrap;gap:4px;align-items:baseline}
.sup-pas header em{margin-left:auto;font:11px var(--font-mono,monospace);font-style:normal;color:var(--ink-muted,#9a9a9a)}
.sup-edad{color:#eab308;font-family:var(--font-mono,monospace);font-size:11px}
.sup-frag{font-size:14px;line-height:1.5;margin:6px 0;color:var(--ink,#f5f5f5)}
.sup-frag mark{background:rgba(234,179,8,.22);color:inherit;padding:0 1px}
.sup-tipos{display:flex;flex-wrap:wrap;gap:4px}.sup-tipos span.ya{color:var(--ink-muted,#9a9a9a);border-style:dashed}.sup-tipos span.nueva{color:#eab308;border-color:rgba(234,179,8,.5)}.sup-tipos span{font:10.5px var(--font-mono,monospace);border:1px solid var(--rule,#292929);border-radius:2px;padding:0 5px;color:var(--ink-soft,#d0d0d0)}
.sup-pas dl{display:grid;grid-template-columns:78px 1fr;gap:2px 8px;font-size:12.5px;margin:6px 0 0}
.sup-pas dt{font:10px var(--font-mono,monospace);text-transform:uppercase;letter-spacing:.06em;color:var(--ink-muted,#9a9a9a);padding-top:2px}
.sup-pas dd{margin:0;color:var(--ink-soft,#d0d0d0)}
.sup-acc{display:flex;gap:12px;margin-top:6px;font:11px var(--font-mono,monospace)}
.sup-acc button{background:none;border:0;color:var(--mark-lt,#60a5fa);cursor:pointer;padding:0;font:inherit}
.sup-acc a{color:var(--mark-lt,#60a5fa)}
.sup-completo{white-space:pre-wrap;font-size:13.5px;line-height:1.55;margin-top:8px;padding-top:8px;border-top:1px solid var(--rule,#292929);color:var(--ink-soft,#d0d0d0);max-height:340px;overflow:auto}
.sup-texto{font-size:14.5px;line-height:1.6;max-height:360px;overflow:auto;border:1px solid var(--rule,#292929);padding:10px 12px;border-radius:3px;background:var(--page,#0d0d0d)}
.sup-h{border-radius:2px;padding:0 1px}.sup-h.conv{box-shadow:inset 0 -2px 0 #eab308}.sup-h.nuc{box-shadow:inset 0 -2px 0 #3b82f6}.sup-h.sel{background:rgba(234,179,8,.3)}
`;
    document.head.appendChild(s);
  }

  window.Superficie = { cargar, analizar, pintar: (el, r, op) => { estilos(); pintar(el, r, op); }, tokens, _clave: clave };
})();
