/* worker/comentarios.js — comentarios sobre cualquier cosa del sitio.

   Distinto de «dejar una frase» (cifrada, al correo de la autora, sobre un
   pasaje): esto es un cuadro que se abre en cualquier página (clic
   sostenido, ver sitio/comentar.js) y llega acá, sin pasar por ningún
   correo. Lo decidido con la autora (2026-10-04):

   · Privado por defecto. Si el lector tilda «que se publique», queda en
     una cola que solo ve la autora: nada se publica sin que ella lo
     apruebe. Los aprobados se leen en comentarios.html, aparte de los
     textos (guardan de qué página vinieron, pero no se pegan encima).
   · Nadie da datos personales. La firma no se pide ni se prohíbe: si
     alguien firma, se guarda y se muestra, también en un privado (criterio
     de la autora, 2026-10-04). Correos y teléfonos escritos en el
     comentario se tachan antes de guardar.
   · Contra bots, sin cookies, cuentas ni captcha de terceros: un cálculo
     corto en el navegador (prueba de trabajo), un tope por zona y hora
     (se cuenta la celda, no quién), un campo trampa, tope de largo y
     rechazo de enlaces. La revisión de la autora es la defensa final.
   · Bitácora mensual pública: cuántos llegaron, cuántos privados, cuántos
     pidieron publicarse, cuántos se aprobaron o rechazaron. Sin horas ni
     zonas.

   Rutas:
     POST /api/comentario                   un lector deja un comentario
     GET  /api/comentarios                  los aprobados (público)
     GET  /api/bitacora?mes=AAAA-MM         la cuenta del mes (público)
     GET  /api/comentarios/cola?mes=AAAA-MM todo el mes (solo la autora)
     POST /api/comentarios/revisar          aprobar, rechazar o borrar
                                            (solo la autora)

   Guardado en el mismo KV que la huella (binding HUELLA):
     c:AAAA-MM:<id>  un comentario; su estado va en la metadata
                     (privado, pendiente, aprobado, rechazado), así la
                     bitácora se cuenta con un solo listado.
     publicos        la lista de aprobados; solo la escribe la autora.
     cz:<zona>:<hora> cuántos envíos llegaron de esa zona en esa hora. */

export const BITS = 16;               // ceros iniciales del hash: ~65 mil intentos, un segundo
const MAX_TEXTO = 1500, MAX_FIRMA = 60;
const MAX_POR_ZONA_HORA = 12;
const RUTA = /^\/[A-Za-z0-9._~%\-\/]{0,180}$/;
const MES = /^\d{4}-\d{2}$/;
const ID = /^[0-9a-f]{16}$/;
const ENLACE = /(https?:\/\/|www\.|\b[a-z0-9-]{2,}\.(com|net|org|info|io|ru|cn|xyz|top|site|online|shop|biz|me|co|ar|es|ly|gl|link|click)\b|\[url|<a\s)/i;

const diaAR = (t) => new Date((t || Date.now()) - 3 * 3600 * 1000).toISOString().slice(0, 10);

const json = (datos, estado, extra) => new Response(JSON.stringify(datos), {
  status: estado || 200,
  headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8', 'X-Content-Type-Options': 'nosniff' }, extra || {}),
});

async function sha256hex(texto) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
}

// cuántos bits en cero al principio del hash (en hexadecimal)
export function cerosIniciales(hex) {
  let n = 0;
  for (const c of hex) {
    const v = parseInt(c, 16);
    if (v === 0) { n += 4; continue; }
    return n + Math.clz32(v) - 28;
  }
  return n;
}

// lo que la prueba de trabajo firma: si cambia una letra, hay que recalcular
export const sobre = (d) => [d.ts, d.p, d.texto, d.firma || '', d.publico ? 1 : 0, d.n].join('|');

// correos y teléfonos escritos en el comentario: se tachan
export function tachar(t) {
  return t
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, '[dato quitado]')
    .replace(/(\+?\d[\d\s().-]{6,}\d)/g, (m) => (m.replace(/\D/g, '').length >= 7 ? '[dato quitado]' : m));
}

async function enviar(request, env) {
  const origen = request.headers.get('Origin');
  if (origen && new URL(origen).host !== new URL(request.url).host) return json({ error: 'origen' }, 403);
  let d;
  try {
    const t = await request.text();
    if (t.length > 8000) return json({ error: 'largo' }, 413);
    d = JSON.parse(t);
  } catch (e) {
    return json({ error: 'json' }, 400);
  }
  if (!d || typeof d !== 'object') return json({ error: 'json' }, 400);
  // campo trampa: una persona no lo ve; un bot que lo llena cree que salió
  if (d.web) return json({ ok: true, estado: 'privado' });

  const texto = String(d.texto || '').replace(/\r\n?/g, '\n').trim();
  const firma = String(d.firma || '').replace(/\s+/g, ' ').trim();
  const p = String(d.p || '').replace(/\/index\.html$/, '/').replace(/\.html$/, '');
  if (texto.length < 2) return json({ error: 'vacío' }, 422);
  if (texto.length > MAX_TEXTO || firma.length > MAX_FIRMA) return json({ error: 'largo' }, 422);
  // un correo no es un enlace: se tacha más abajo, así que no cuenta acá
  if (ENLACE.test(tachar(texto)) || ENLACE.test(tachar(firma))) return json({ error: 'enlaces' }, 422);
  if (!RUTA.test(p)) return json({ error: 'página' }, 422);
  const ts = Number(d.ts);
  if (!isFinite(ts) || Math.abs(Date.now() - ts) > 15 * 60 * 1000) return json({ error: 'hora' }, 422);

  const hash = await sha256hex(sobre({ ts, p: d.p, texto: d.texto, firma: d.firma, publico: d.publico, n: d.n }));
  if (cerosIniciales(hash) < BITS) return json({ error: 'cálculo' }, 422);
  if (!env.HUELLA) return json({ error: 'sin almacenamiento' }, 503);

  // tope por zona y hora: se cuenta la celda (país, región, ciudad), no quién
  const cf = request.cf || {};
  const zona = [cf.country || '??', cf.region || '', cf.city || ''].join('|').slice(0, 120);
  const hora = new Date(Date.now() - 3 * 3600 * 1000).toISOString().slice(0, 13);
  const kz = 'cz:' + zona + ':' + hora;
  const enZona = parseInt(await env.HUELLA.get(kz), 10) || 0;
  if (enZona >= MAX_POR_ZONA_HORA) return json({ error: 'muchos' }, 429);

  const id = hash.slice(0, 16);
  const dia = diaAR();
  const clave = 'c:' + dia.slice(0, 7) + ':' + id;
  if (await env.HUELLA.get(clave)) return json({ error: 'repetido' }, 409);

  const publico = !!d.publico;
  const c = {
    id, d: dia, p,
    texto: tachar(texto),
    // la firma, si la dejaron, va también en un privado (tachada como el texto)
    firma: firma ? tachar(firma) : '',
    publico,
    matriz: !!d.matriz,
  };
  const e = publico ? 'pendiente' : 'privado';
  try {
    await env.HUELLA.put(clave, JSON.stringify(c), { metadata: { e, m: c.matriz ? 1 : 0 } });
    await env.HUELLA.put(kz, String(enZona + 1), { expirationTtl: 2 * 3600 });
  } catch (err) {
    return json({ error: 'guardar' }, 503);
  }
  return json({ ok: true, estado: e });
}

async function listar(env, prefijo) {
  const keys = [];
  let cursor;
  do {
    const r = await env.HUELLA.list({ prefix: prefijo, cursor });
    keys.push(...r.keys);
    cursor = r.list_complete ? null : r.cursor;
  } while (cursor);
  return keys;
}

async function publicos(env) {
  if (!env.HUELLA) return json({ comentarios: [] });
  const l = (await env.HUELLA.get('publicos', { type: 'json', cacheTtl: 60 })) || [];
  return json({ comentarios: l }, 200, { 'Cache-Control': 'public, max-age=120' });
}

const bitacoras = new Map(); // mes → {t, datos}

async function bitacora(request, env) {
  const mes = new URL(request.url).searchParams.get('mes') || diaAR().slice(0, 7);
  if (!MES.test(mes)) return json({ error: 'mes' }, 400);
  if (!env.HUELLA) return json({ mes, llegaron: 0 });
  const enCache = bitacoras.get(mes);
  if (enCache && Date.now() - enCache.t < 10 * 60 * 1000) return json(enCache.datos, 200, { 'Cache-Control': 'public, max-age=600' });
  const keys = await listar(env, 'c:' + mes + ':');
  const datos = { mes, llegaron: keys.length, privados: 0, pidieron_publicarse: 0, aprobados: 0, rechazados: 0, pendientes: 0 };
  keys.forEach(k => {
    const e = (k.metadata || {}).e;
    if (e === 'privado') datos.privados++;
    else {
      datos.pidieron_publicarse++;
      if (e === 'aprobado') datos.aprobados++;
      else if (e === 'rechazado') datos.rechazados++;
      else datos.pendientes++;
    }
  });
  bitacoras.set(mes, { t: Date.now(), datos });
  return json(datos, 200, { 'Cache-Control': 'public, max-age=600' });
}

async function cola(request, env, esAutora) {
  if (!(await esAutora(request))) return json({ error: 'solo la autora' }, 401, { 'Cache-Control': 'no-store' });
  const mes = new URL(request.url).searchParams.get('mes') || diaAR().slice(0, 7);
  if (!MES.test(mes)) return json({ error: 'mes' }, 400);
  const keys = await listar(env, 'c:' + mes + ':');
  const lista = await Promise.all(keys.map(async k => {
    const c = await env.HUELLA.get(k.name, { type: 'json' });
    return c && Object.assign(c, { estado: (k.metadata || {}).e || 'privado' });
  }));
  return json({ mes, comentarios: lista.filter(Boolean).sort((a, b) => (b.d || '').localeCompare(a.d || '')) }, 200, { 'Cache-Control': 'no-store' });
}

async function revisar(request, env, esAutora) {
  if (!(await esAutora(request))) return json({ error: 'solo la autora' }, 401, { 'Cache-Control': 'no-store' });
  let d;
  try { d = JSON.parse(await request.text()); } catch (e) { return json({ error: 'json' }, 400); }
  const { mes, id, accion } = d || {};
  if (!MES.test(mes || '') || !ID.test(id || '') || !['aprobar', 'rechazar', 'borrar'].includes(accion)) return json({ error: 'pedido' }, 400);
  const clave = 'c:' + mes + ':' + id;
  const c = await env.HUELLA.get(clave, { type: 'json' });
  if (!c) return json({ error: 'no está' }, 404);
  let lista = (await env.HUELLA.get('publicos', { type: 'json' })) || [];
  lista = lista.filter(x => x.id !== id);
  if (accion === 'borrar') {
    await env.HUELLA.delete(clave);
  } else if (accion === 'aprobar') {
    if (!c.publico) return json({ error: 'es privado' }, 422);
    lista.unshift({ id, d: c.d, p: c.p, texto: c.texto, firma: c.firma || '' });
    await env.HUELLA.put(clave, JSON.stringify(c), { metadata: { e: 'aprobado', m: c.matriz ? 1 : 0 } });
  } else {
    // rechazado (o retirado después de aprobarse): queda como privado
    await env.HUELLA.put(clave, JSON.stringify(c), { metadata: { e: c.publico ? 'rechazado' : 'privado', m: c.matriz ? 1 : 0 } });
  }
  await env.HUELLA.put('publicos', JSON.stringify(lista));
  bitacoras.delete(mes);
  return json({ ok: true });
}

// null si la ruta no es de comentarios
export function comentarios(request, env, esAutora) {
  const ruta = new URL(request.url).pathname;
  if (ruta === '/api/comentario') return request.method === 'POST' ? enviar(request, env) : json({ error: 'método' }, 405);
  if (ruta === '/api/comentarios') return publicos(env);
  if (ruta === '/api/bitacora') return bitacora(request, env);
  if (ruta === '/api/comentarios/cola') return cola(request, env, esAutora);
  if (ruta === '/api/comentarios/revisar') return request.method === 'POST' ? revisar(request, env, esAutora) : json({ error: 'método' }, 405);
  return null;
}
