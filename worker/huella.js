/* worker/huella.js — la huella colectiva de p314b.

   Todo el sitio son archivos estáticos (web/, los sirve Cloudflare tal
   cual). Este Worker atiende /api/huella (abajo), /api/visita(s) y
   /api/lectura(s) (más abajo, cada una con su explicación), y los
   comentarios (/api/comentario…, en worker/comentarios.js):

   · POST: un navegador avisa los pasos que dio entre textos, como pares
     [de, a] de slugs («de Términos y condiciones pasó a Ni-ni»). No se
     guarda quién, ni cuándo, ni desde dónde: ni IP, ni hora, ni cookies.
     Solo se suma 1 a la cuenta de cada par.
   · GET: devuelve la suma de todos los pares, para que huella.html
     dibuje los caminos gastados y las zonas vírgenes de todos.

   Los slugs se validan contra corpus.json (solo textos en línea), y un
   pedido lleva a lo sumo 20 pares. La cuenta vive en un solo valor de
   KV (binding HUELLA, lo crea solo el primer `wrangler deploy`). Si dos
   pedidos llegan a la vez, alguno puede perderse: es una huella, no una
   contabilidad. El plan gratis permite 1000 escrituras por día; pasado
   eso, el día no suma más y el sitio sigue igual. */

import { comentarios } from './comentarios.js';

const CLAVE = 'pares';
const SLUG = /^[a-z0-9-]{1,80}$/;
let validos = null, validosHasta = 0;

async function slugsEnLinea(env, url) {
  if (validos && Date.now() < validosHasta) return validos;
  try {
    const r = await env.ASSETS.fetch(new Request(new URL('/corpus.json', url)));
    const c = await r.json();
    validos = new Set((c.obras || []).filter(o => !o.diagonal && o.en_linea !== false).map(o => o.id));
    validosHasta = Date.now() + 10 * 60 * 1000;
  } catch (e) {
    validos = validos || new Set();
  }
  return validos;
}

const json = (datos, estado, extra) => new Response(JSON.stringify(datos), {
  status: estado || 200,
  headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8', 'X-Content-Type-Options': 'nosniff' }, extra || {}),
});

async function huella(request, env) {
  if (!env.HUELLA) return json({ error: 'sin almacenamiento' }, 503);
  if (request.method === 'GET') {
    const datos = (await env.HUELLA.get(CLAVE, { type: 'json', cacheTtl: 300 })) || { pares: {}, desde: null };
    return json(datos, 200, { 'Cache-Control': 'public, max-age=300' });
  }
  if (request.method !== 'POST') return json({ error: 'método' }, 405);
  // solo desde el propio sitio
  const origen = request.headers.get('Origin');
  if (origen && new URL(origen).host !== new URL(request.url).host) return json({ error: 'origen' }, 403);
  let cuerpo;
  try {
    const texto = await request.text();
    if (texto.length > 4000) return json({ error: 'largo' }, 413);
    cuerpo = JSON.parse(texto);
  } catch (e) {
    return json({ error: 'json' }, 400);
  }
  const ok = await slugsEnLinea(env, request.url);
  const pares = (Array.isArray(cuerpo && cuerpo.pares) ? cuerpo.pares : []).slice(0, 20)
    .filter(p => Array.isArray(p) && p.length === 2 && SLUG.test(p[0]) && SLUG.test(p[1]) && p[0] !== p[1] && ok.has(p[0]) && ok.has(p[1]));
  if (!pares.length) return new Response(null, { status: 204 });
  try {
    const datos = (await env.HUELLA.get(CLAVE, { type: 'json' })) || { pares: {}, desde: new Date().toISOString().slice(0, 10) };
    pares.forEach(([de, a]) => { const k = de + '|' + a; datos.pares[k] = (datos.pares[k] || 0) + 1; });
    await env.HUELLA.put(CLAVE, JSON.stringify(datos));
  } catch (e) {
    // sin cupo de escrituras o KV caído: no pasa nada visible
  }
  return new Response(null, { status: 204 });
}

/* ── Visitas: un contador simple para la autora ──
   POST /api/visita {p: ruta, r: sitio de donde vino}: suma 1 a la ruta, al
   sitio de origen (solo el dominio) y al país (lo dice Cloudflare), en la
   cuenta del día (hora de Argentina). No se guarda IP, hora exacta ni
   cookies. GET /api/visitas: solo con el token de GitHub de la autora
   (el mismo de acceso.html): el Worker le pregunta a GitHub si ese token
   puede escribir en el repo. */
const REPO = 'p4p13b/p314b';
const RUTA = /^\/[A-Za-z0-9._~%\-\/]{0,180}$/;
const diaAR = (t) => new Date((t || Date.now()) - 3 * 3600 * 1000).toISOString().slice(0, 10);
const autorizados = new Map(); // huella del token → vence

async function esAutora(request) {
  const m = /^Bearer\s+(\S{20,})$/.exec(request.headers.get('Authorization') || '');
  if (!m) return false;
  const k = m[1].slice(-12);
  if ((autorizados.get(k) || 0) > Date.now()) return true;
  const r = await fetch('https://api.github.com/repos/' + REPO, { headers: { Authorization: 'Bearer ' + m[1], 'User-Agent': 'p314b-visitas', Accept: 'application/vnd.github+json' } });
  if (!r.ok) return false;
  const d = await r.json();
  if (!(d.permissions && (d.permissions.push || d.permissions.admin))) return false;
  autorizados.set(k, Date.now() + 10 * 60 * 1000);
  return true;
}

async function visita(request, env) {
  if (!env.HUELLA) return new Response(null, { status: 204 });
  if (request.method !== 'POST') return json({ error: 'método' }, 405);
  const origen = request.headers.get('Origin');
  if (origen && new URL(origen).host !== new URL(request.url).host) return json({ error: 'origen' }, 403);
  let d;
  try { const t = await request.text(); if (t.length > 1000) return json({ error: 'largo' }, 413); d = JSON.parse(t); } catch (e) { return json({ error: 'json' }, 400); }
  // /index.html y / son la misma página; /obras/x.html y /obras/x también
  const p = String(d && d.p || '').replace(/\/index\.html$/, '/').replace(/\.html$/, '');
  if (!RUTA.test(p)) return new Response(null, { status: 204 });
  let ref = '';
  try { if (d.r) { const h = new URL(d.r).host; if (h && h !== new URL(request.url).host) ref = h.slice(0, 80); } } catch (e) {}
  const pais = (request.cf && request.cf.country) || '??';
  const clave = 'v:' + diaAR();
  try {
    const c = (await env.HUELLA.get(clave, { type: 'json' })) || { total: 0, rutas: {}, desde: {}, paises: {} };
    c.total++;
    c.rutas[p] = (c.rutas[p] || 0) + 1;
    if (ref) c.desde[ref] = (c.desde[ref] || 0) + 1;
    c.paises[pais] = (c.paises[pais] || 0) + 1;
    await env.HUELLA.put(clave, JSON.stringify(c), { expirationTtl: 400 * 86400 });
  } catch (e) {}
  return new Response(null, { status: 204 });
}

async function visitas(request, env) {
  if (!(await esAutora(request))) return json({ error: 'solo la autora' }, 401, { 'Cache-Control': 'no-store' });
  const n = Math.min(90, Math.max(1, parseInt(new URL(request.url).searchParams.get('dias') || '30', 10) || 30));
  const dias = [];
  for (let i = 0; i < n; i++) dias.push(diaAR(Date.now() - i * 86400000));
  const datos = await Promise.all(dias.map(dia => env.HUELLA.get('v:' + dia, { type: 'json' }).then(c => ({ dia, ...(c || { total: 0, rutas: {}, desde: {}, paises: {} }) }))));
  return json({ dias: datos }, 200, { 'Cache-Control': 'no-store' });
}

/* ── Lecturas: cómo se lee cada texto (para la matriz de lectores) ──
   POST /api/lectura {lecturas: [{t: slug, s: segundos, i: {tipo: cuenta}}]}:
   por cada texto leído guarda un registro con la hora (hora entera de
   Argentina), la zona (país, región y ciudad que dice Cloudflare), el clima
   de esa zona en ese momento (Open-Meteo, solo con la celda redondeada a
   ~10 km: nunca la IP) y qué se hizo adentro del texto (seguir una
   diagonal, hojear, abrir una nota, tocar un pariente, copiar…).
   «pasiva»: se leyó sin interactuar con nada.
   NO se guarda: IP, hora exacta, identificador de persona, de sesión ni de
   dispositivo, ni cookies. No hay forma de unir dos registros del mismo
   lector. GET /api/lecturas: solo con el token de la autora; no es público. */
const INTERACCIONES = ['diagonal', 'hojear', 'nota', 'marca', 'pariente', 'mismizar', 'opcion', 'copiar', 'capitulo'];
const MAX_POR_DIA = 3000;
const climas = new Map(); // celda y hora → {t, ll, k, v}

async function climaDe(lat, lon) {
  if (!isFinite(lat) || !isFinite(lon)) return null;
  const la = Math.round(lat * 10) / 10, lo = Math.round(lon * 10) / 10;
  const clave = la + ',' + lo + '@' + Math.floor(Date.now() / 3600000);
  if (climas.has(clave)) return climas.get(clave);
  let c = null;
  try {
    const ac = new AbortController(), t = setTimeout(() => ac.abort(), 1500);
    const r = await fetch('https://api.open-meteo.com/v1/forecast?latitude=' + la + '&longitude=' + lo + '&current=temperature_2m,precipitation,weather_code,wind_speed_10m', { signal: ac.signal });
    clearTimeout(t);
    if (r.ok) {
      const d = (await r.json()).current || {};
      // t: °C · ll: mm de lluvia · k: código del clima (WMO) · v: viento km/h
      c = { t: d.temperature_2m, ll: d.precipitation, k: d.weather_code, v: d.wind_speed_10m };
    }
  } catch (e) {}
  if (climas.size > 500) climas.clear();
  climas.set(clave, c);
  return c;
}

async function lectura(request, env) {
  if (!env.HUELLA) return new Response(null, { status: 204 });
  if (request.method !== 'POST') return json({ error: 'método' }, 405);
  const origen = request.headers.get('Origin');
  if (origen && new URL(origen).host !== new URL(request.url).host) return json({ error: 'origen' }, 403);
  let cuerpo;
  try {
    const texto = await request.text();
    if (texto.length > 4000) return json({ error: 'largo' }, 413);
    cuerpo = JSON.parse(texto);
  } catch (e) {
    return json({ error: 'json' }, 400);
  }
  const ok = await slugsEnLinea(env, request.url);
  const regs = (Array.isArray(cuerpo && cuerpo.lecturas) ? cuerpo.lecturas : []).slice(0, 20)
    .filter(r => r && SLUG.test(String(r.t)) && ok.has(r.t))
    .map(r => {
      const i = {};
      INTERACCIONES.forEach(k => { const n = Math.min(99, parseInt(r.i && r.i[k], 10) || 0); if (n > 0) i[k] = n; });
      const s = Math.min(3600, Math.max(0, Math.round(Number(r.s) || 0)));
      return { t: r.t, s, i, pasiva: s >= 15 && !Object.keys(i).length };
    })
    .filter(r => r.s >= 3 || Object.keys(r.i).length);
  if (!regs.length) return new Response(null, { status: 204 });
  const cf = request.cf || {};
  const zona = [cf.country || '??', cf.region || '', cf.city || ''];
  const clima = await climaDe(parseFloat(cf.latitude), parseFloat(cf.longitude));
  const hora = new Date(Date.now() - 3 * 3600 * 1000).getUTCHours();
  const clave = 'l:' + diaAR();
  try {
    const d = (await env.HUELLA.get(clave, { type: 'json' })) || [];
    if (d.length < MAX_POR_DIA) {
      regs.forEach(r => d.push(Object.assign({ h: hora, z: zona, c: clima }, r)));
      await env.HUELLA.put(clave, JSON.stringify(d), { expirationTtl: 800 * 86400 });
    }
  } catch (e) {}
  return new Response(null, { status: 204 });
}

async function lecturas(request, env) {
  if (!(await esAutora(request))) return json({ error: 'solo la autora' }, 401, { 'Cache-Control': 'no-store' });
  const n = Math.min(90, Math.max(1, parseInt(new URL(request.url).searchParams.get('dias') || '30', 10) || 30));
  const dias = [];
  for (let i = 0; i < n; i++) dias.push(diaAR(Date.now() - i * 86400000));
  const datos = await Promise.all(dias.map(dia => env.HUELLA.get('l:' + dia, { type: 'json' }).then(l => ({ dia, lecturas: l || [] }))));
  return json({ dias: datos }, 200, { 'Cache-Control': 'no-store' });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/huella') return huella(request, env);
    if (url.pathname === '/api/visita') return visita(request, env);
    if (url.pathname === '/api/visitas') return visitas(request, env);
    if (url.pathname === '/api/lectura') return lectura(request, env);
    if (url.pathname === '/api/lecturas') return lecturas(request, env);
    const c = comentarios(request, env, esAutora);
    if (c) return c;
    return env.ASSETS.fetch(request);
  },
};
