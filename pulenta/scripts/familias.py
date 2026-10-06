"""Tanda 1 de pulenta · familias con excepciones: «el lema une, el uso separa».

Para pulenta (PLAN_pulenta.md, 27-sep). La raíz compartida solo PROPONE
candidatos; lo que decide si dos miembros son lo mismo es el vecindario de
uso en el cuerpo (mismo / mismidad / mismizar; indiferir / indiferencia).

1. Lemas: los de la página (lematica.lema: reglas + lemas.json de la
   autora). Cuentan las palabras de contenido; «mismo/misma/otro/nada» sí.
2. Candidatos: se le sacan al lema los sufijos derivativos (‑ización, ‑idad,
   ‑encia, ‑miento, ‑izar, ‑ble…) y las terminaciones (‑ar/‑er/‑ir, ‑o/‑a);
   lo que queda (≥ 4 letras) es la raíz. Misma raíz → misma familia
   candidata. Los prefijos no se sacan (diferir e indiferir son raíces
   distintas: la autora los distingue).
3. Uso: para cada miembro con ≥ MINF apariciones, sus vecinos (±4 palabras
   de contenido, sin los de su propia familia, para que el parentesco no
   cuente como uso), como media de sus vectores de palabras (E.npy, fase 2),
   centrada. El vecindario PPMI queda solo para listar los vecinos.
4. Decisión, con mitades: las obras se parten al azar en dos mitades,
   N_PARTES veces. Para cada par (a, b) de la familia:
     propio(a)  coseno de a en una mitad con a en la otra (cuánto se parece
                el uso de a a sí mismo)
     cruce(a,b) coseno de a en una mitad con b en la otra
     d          media de propio(a), propio(b) − cruce(a, b)
   Si d es positivo y estable entre particiones (d / desvío ≥ 2, y d ≥ 15 %
   de lo propio): «el uso separa». Si d ≤ 5 % de lo propio: «une». Si no,
   «dudoso». Con poco texto de uno de los dos: «insuficiente».
5. Subfamilias de uso: los miembros unidos por «une» (componentes conexas).

Además, una ficha por obra (fecha, carpeta, verso o prosa estimado por el
largo de las líneas del texto original, palabras) para el resto del plan.

Escribe pulenta/datos/familias.json, pulenta/datos/familias-revision.csv
(una fila por miembro, con columnas vacías para la decisión de la autora) y
pulenta/datos/obras.json. Se corre a mano, desde cualquier carpeta:
python3 pulenta/scripts/familias.py

Lo que toma del lado del sitio (ver INTERFAZ.md): cache-matriz/pasajes.json
(matriz/indexar_pasajes.py), cache-matriz/anexo/fechas.json (anexo/fechas.py),
cache-matriz/anexo/estructural.json (anexo/estructural.py), sitio/lemas.json
y los módulos lematica y _rutas del anexo, que se importan de
sitio/matriz/anexo/scripts/ sin copiarlos.
"""
import os, sys
# Mismo resultado en cada corrida: el orden de los conjuntos de palabras (y con él
# las sumas que deciden «une» o «separa» cerca del umbral) depende del hash de
# Python, que cambia por proceso salvo que se fije.
if os.environ.get('PYTHONHASHSEED') != '0':
    os.execve(sys.executable, [sys.executable] + sys.argv, dict(os.environ, PYTHONHASHSEED='0'))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                '..', '..', 'sitio', 'matriz', 'anexo', 'scripts')))
from _rutas import RAIZ  # rutas y carpeta de trabajo (cache-matriz/anexo/)
import collections, csv, html, json, math, os, random, re, statistics, sys, zlib
import numpy as np
from lematica import TOKEN, cuenta, lema, norm, F as FORMAS_AUTORA

random.seed(1)
MINF = 6          # apariciones mínimas para medir el uso
VENT = 4          # vecinos a cada lado
N_PARTES = 8      # particiones en mitades
UNE = 0.85        # parecido corregido desde el cual el uso une
SEPARA = 0.70     # techo por debajo del cual el uso separa
PISO = 0.15       # autoparecido mínimo para que la medida no sea ruido
SALIDA = os.path.join(RAIZ, 'pulenta', 'datos')
os.makedirs(SALIDA, exist_ok=True)

P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
PAS, META = P['pasajes'], P['meta']['sitios']
FECHAS = json.load(open('fechas.json'))
for slug, f in (('cuerpo', '2019-11-15'), ('torcion', '2019-12-10'), ('3rd-comment', '2020-01-10'),
                ('autopoiesis', '2020-02-10'), ('bried-frain', '2020-03-10')):
    FECHAS.setdefault(slug, {'punto': f, 'carpeta': 'I - Estudio', 'fuente': 'orden', 'confianza': 'baja'})

# ── sufijos para proponer la raíz (solo propone) ──
DERIV = sorted(['izaciones', 'izacion', 'aciones', 'acion', 'iciones', 'icion', 'ciones', 'cion', 'siones', 'sion',
                'bilidades', 'bilidad', 'idades', 'idad', 'encias', 'encia', 'ancias', 'ancia', 'mientos', 'miento',
                'mente', 'izante', 'izado', 'izada', 'izar', 'ismos', 'ismo', 'istas', 'ista', 'ibles', 'ible', 'ables',
                'able', 'ivos', 'ivas', 'ivo', 'iva', 'entes', 'ente', 'antes', 'ante', 'ales', 'al', 'osos', 'osas',
                'oso', 'osa', 'ores', 'or', 'ica', 'ico', 'icas', 'icos', 'ez', 'eza', 'ura', 'idor', 'idora',
                'ados', 'adas', 'ado', 'ada', 'idos', 'idas', 'ido', 'ida', 'iendo', 'ando'],
               key=len, reverse=True)
FLEX = ['ar', 'er', 'ir', 'os', 'as', 'es', 'o', 'a', 'e', 's']


def raiz(l):
    r = norm(l)
    n0 = len(r)
    for _ in range(2):  # «diferenciación» → diferencia → difer
        for s in DERIV:
            if r.endswith(s) and len(r) - len(s) >= 4:
                r = r[:-len(s)]
                break
    for s in FLEX if len(r) == n0 else ():  # sin flexión tras un sufijo: indiferencia → indifer, no «indif»
        if r.endswith(s) and len(r) - len(s) >= 4:
            r = r[:-len(s)]
            break
    return r[:7]  # «indiferenciado», «indiferible», «indiferencia» → indifer


# ── texto por obra y lemas ──
por_obra = collections.defaultdict(list)
for p in PAS:
    por_obra[p['sitio']].append(p)
for o in por_obra:
    por_obra[o].sort(key=lambda p: (p.get('pdf_pagina') or 0, p['id']))

# Unidad: la FORMA del texto, no el lema de la matriz. El lematizador de la
# página lleva «-ía» a infinitivo y con eso rompe las palabras en «-ia»
# (indiferencia → «indiferencer», existencia → «exister»): para las familias,
# donde la morfología es justamente lo que se pone a prueba, no sirve. Se
# usa la forma en minúsculas, con el plural plegado al singular cuando el
# singular existe en el cuerpo (signos → signo), y las decisiones de la
# autora en lemas.json (formas → lema) por encima de todo.
_crudas = collections.Counter()
for p in PAS:
    for m in TOKEN.finditer(p['texto']):
        if cuenta(m.group()):
            _crudas[m.group().lower()] += 1
AUTORA = {k.lower(): v.lower() for k, v in FORMAS_AUTORA.items()}


def unidad(w):
    w = w.lower()
    if w in AUTORA:
        return AUTORA[w]
    if w.endswith('es') and len(w) > 5 and _crudas.get(w[:-2]):
        return AUTORA.get(w[:-2], w[:-2])
    if w.endswith('s') and len(w) > 4 and _crudas.get(w[:-1]):
        return AUTORA.get(w[:-1], w[:-1])  # indiferentes → indiferente → (autora) indiferencia
    return w


seqs = {}                       # obra → [unidades de contenido en orden]
formas = collections.defaultdict(collections.Counter)
frec = collections.Counter()
obras_de = collections.defaultdict(set)
PRIMERAS = collections.defaultdict(list)  # lema → hasta 2 apariciones (obra, pasaje, inicio, fin), una por obra
for o, lst in sorted(por_obra.items(), key=lambda kv: (FECHAS.get(kv[0]) or {}).get('punto') or '9'):
    s = []
    for p in lst:
        for m in TOKEN.finditer(p['texto']):
            w = m.group()
            if not cuenta(w):
                continue
            l = unidad(w)
            pr = PRIMERAS[l]
            if len(pr) < 2 and (not pr or pr[-1][0] != o):
                pr.append((o, p, m.start(), m.end()))
            s.append(l)
            formas[l][w.lower()] += 1
            frec[l] += 1
            obras_de[l].add(o)
        s.append(None)  # corte entre pasajes
    seqs[o] = s
por_obra_frec = collections.defaultdict(collections.Counter)
tok_obra = {}
for o, s_ in seqs.items():
    tok_obra[o] = sum(1 for x in s_ if x) or 1
    for x in s_:
        if x:
            por_obra_frec[x][o] += 1
ver = lambda l: formas[l].most_common(1)[0][0] if formas[l] else l

# ── familias candidatas ──
fam = collections.defaultdict(set)
for l in frec:
    if len(l) >= 4 and frec[l] >= 2:
        fam[raiz(l)].add(l)
fam = {r: ms for r, ms in fam.items() if len(ms) >= 2 and sum(1 for l in ms if frec[l] >= MINF) >= 2}
miembro_de = {l: r for r, ms in fam.items() for l in ms}
objetivo = {l for ms in fam.values() for l in ms if frec[l] >= MINF}
print('familias candidatas', len(fam), '| miembros medibles', len(objetivo), file=sys.stderr)

# ── contextos por obra (para poder partir en mitades) ──
CTXV = [l for l, _ in frec.most_common(6000)]
CID = {l: i for i, l in enumerate(CTXV)}
ctx = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # lema → obra → Counter(cid)
apar = collections.defaultdict(list)  # lema → [(obra, (cid, …))]: una entrada por aparición
tot_ctx = collections.Counter()
for o, s in seqs.items():
    n = len(s)
    for i, l in enumerate(s):
        if l is None:
            continue
        if l in CID:
            tot_ctx[CID[l]] += 1
        if l not in objetivo:
            continue
        r = miembro_de[l]
        for j in range(max(0, i - VENT), min(n, i + VENT + 1)):
            if j == i:
                continue
            c = s[j]
            if c is None:
                continue
            if c in CID and miembro_de.get(c) != r:
                ctx[l][o][CID[c]] += 1
        # la aparición con su vecindario, para comparar uso donde conviven
        apar[l].append((o, tuple(CID[s[j]] for j in range(max(0, i - VENT), min(n, i + VENT + 1))
                                 if j != i and s[j] is not None and s[j] in CID and miembro_de.get(s[j]) != r)))
N_TOT = sum(tot_ctx.values())

# ── espacio denso: los vectores de palabras de la fase 2 (E.npy) ──
from lematica import clave as _clave
_EST = json.load(open('estructural.json'))
_VID = {c: i for i, c in enumerate(_EST['voc'])}
_E = np.load('E.npy').astype(np.float32)
_E /= np.linalg.norm(_E, axis=1, keepdims=True) + 1e-9
def _fila(l):
    for k in (l, norm(l), re.sub(r'(ar|er|ir)$', '', l)):
        if k in _VID:
            return _VID[k]
    return None
FILA = {CID[l]: _fila(l) for l in CTXV}
# una aparición = la media de los vectores de sus vecinos; se centra con la
# media de todas las apariciones medidas (saca la dirección común del cuerpo)
def vec_aparicion(cc):
    fs = [FILA[c] for c in cc if FILA.get(c) is not None]
    return _E[fs].mean(0) if fs else None
APV = {}
for l in objetivo:
    APV[l] = [(o, v) for o, v in ((o, vec_aparicion(cc)) for o, cc in apar[l]) if v is not None]
_todas = np.array([v for l in APV for _, v in APV[l][:50]])
CENTRO_USO = _todas.mean(0) if len(_todas) else 0
LOGP = {k: math.log(v / N_TOT) for k, v in tot_ctx.items()}


def vector(l, obras):
    """Vecindario de uso de l en esas obras: PPMI disperso y normalizado."""
    c = collections.Counter()
    por = ctx[l]
    for o in obras:
        if o in por:
            c.update(por[o])
    t = sum(c.values())
    if t < 3:
        return None
    lt = math.log(t)
    w = {k: x for k, x in ((k, math.log(n) - lt - LOGP[k]) for k, n in c.items()) if x > 0}
    nrm = math.sqrt(sum(x * x for x in w.values()))
    return {k: x / nrm for k, x in w.items()} if nrm else None


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(k, 0) for k, x in a.items())


OBRAS = sorted(seqs)
particiones = []
for _ in range(N_PARTES):
    o = OBRAS[:]
    random.shuffle(o)
    particiones.append((set(o[:len(o) // 2]), set(o[len(o) // 2:])))
_VEC = {}


def VEC(l, k, h):
    if (l, k, h) not in _VEC:
        _VEC[(l, k, h)] = vector(l, particiones[k][h] & set(ctx[l]))
    return _VEC[(l, k, h)]


def ppmi(c):
    t = sum(c.values())
    if t < 3:
        return None
    lt = math.log(t)
    w = {k: x for k, x in ((k, math.log(n) - lt - LOGP[k]) for k, n in c.items()) if x > 0}
    nrm = math.sqrt(sum(x * x for x in w.values()))
    return {k: x / nrm for k, x in w.items()} if nrm else None


def comparar(a, b):
    """Parecido de uso DONDE CONVIVEN, en el espacio denso: solo las
    apariciones de a y de b en las obras donde aparecen las dos (así no se
    mide la diferencia de tema entre libros). Cada aparición es la media de
    los vectores de sus vecinos; se parten al azar en dos mitades, N_PARTES
    veces, y el coseno cruzado de las medias (centradas) se divide por la raíz
    del producto de los autoparecidos: ~1 si se usan igual, menos si no."""
    comunes = {o for o, _ in APV[a]} & {o for o, _ in APV[b]}
    A = np.array([v for o, v in APV[a] if o in comunes])
    B = np.array([v for o, v in APV[b] if o in comunes])
    if len(A) < MINF or len(B) < MINF:
        return {'veredicto': 'insuficiente', 'obras_en_comun': len(comunes), 'apariciones': [len(A), len(B)]}
    # semilla fija por par: hash() de Python cambia en cada corrida (PYTHONHASHSEED)
    # y con él las mitades; crc32 da las mismas siempre
    rnd = np.random.default_rng(zlib.crc32(f'{a}\x00{b}'.encode('utf-8')))
    def cs(x, y):
        x = x - CENTRO_USO; y = y - CENTRO_USO
        return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
    rs, props, cruces = [], [], []
    for _ in range(N_PARTES):
        pa_, pb_ = rnd.permutation(len(A)), rnd.permutation(len(B))
        a0, a1 = A[pa_[:len(A) // 2]].mean(0), A[pa_[len(A) // 2:]].mean(0)
        b0, b1 = B[pb_[:len(B) // 2]].mean(0), B[pb_[len(B) // 2:]].mean(0)
        pa, pb = cs(a0, a1), cs(b0, b1)
        if pa < PISO or pb < PISO:
            continue
        cr = (cs(a0, b1) + cs(a1, b0)) / 2
        rs.append(min(1.5, cr / math.sqrt(pa * pb))); props.append((pa, pb)); cruces.append(cr)
    if len(rs) < N_PARTES // 2:
        return {'veredicto': 'insuficiente', 'obras_en_comun': len(comunes), 'apariciones': [len(A), len(B)]}
    r, sd = statistics.mean(rs), statistics.pstdev(rs)
    hi = r + 2 * sd / math.sqrt(len(rs))
    return {'veredicto': None, 'r': round(r, 3), 'r_techo': round(hi, 3),
            'propio_a': round(statistics.mean(x[0] for x in props), 3), 'propio_b': round(statistics.mean(x[1] for x in props), 3),
            'cruce': round(statistics.mean(cruces), 3), 'obras_en_comun': len(comunes), 'apariciones': [len(A), len(B)],
            'particiones': len(rs)}


def distribucion(a, b):
    """Dónde vive cada uno: coseno de los perfiles por obra (tasa por obra).
    Lo que la medida de uso, al mirar solo donde conviven, deja afuera."""
    pa = {o: c / tok_obra[o] for o, c in por_obra_frec[a].items()}
    pb = {o: c / tok_obra[o] for o, c in por_obra_frec[b].items()}
    num = sum(x * pb.get(o, 0) for o, x in pa.items())
    den = math.sqrt(sum(x * x for x in pa.values()) * sum(x * x for x in pb.values()))
    return round(num / den, 3) if den else None


_CMP = {}


def comparar_cache(a, b):
    k = (a, b) if a < b else (b, a)
    if k not in _CMP:
        _CMP[k] = comparar(*k)
    return dict(_CMP[k])


def es_flexion(a, b):
    """Singular/plural o masculino/femenino de la misma palabra (por la forma
    más usada): la referencia de «mismo uso» para calibrar."""
    x, y = sorted((ver(a), ver(b)), key=len)
    forma = y in (x + 's', x + 'es') or (len(x) == len(y) and x[:-1] == y[:-1] and {x[-1], y[-1]} == {'o', 'a'})
    # y que el lematizador las lleve a una de las dos: mismo/misma sí;
    # callo/calla (→ callar) o puerto/puerta (dos palabras) no
    return forma and lema(x) == lema(y) and lema(x) in (x, y)


def veredicto(c):
    if c.get('r') is None:
        return 'insuficiente'
    if c['r'] >= UNE:
        return 'une'
    if c['r_techo'] < SEPARA:
        return 'el uso separa'
    return 'dudoso'


def vecinos(l, k=8):
    v = vector(l, set(ctx[l])) if l in objetivo else None
    if not v:
        return []
    return [ver(CTXV[i]) for i, _ in sorted(v.items(), key=lambda x: -x[1])[:k]]


def anio(o):
    f = (FECHAS.get(o) or {}).get('punto')
    return f[:7] if f else None


def ejemplo(l, n=2):
    out = []
    for o, p, a0, b0 in PRIMERAS.get(l, [])[:n]:
        t = p['texto']
        a, b = max(0, a0 - 90), min(len(t), b0 + 90)
        out.append({'obra': META.get(o, {}).get('titulo', o), 'pagina': p.get('pdf_pagina'),
                    'texto': ('…' if a else '') + re.sub(r'\s+', ' ', t[a:b]).strip() + ('…' if b < len(t) else '')})
    return out


# ── verso o prosa por obra (estimado) ──
def texto_original(o):
    f = META.get(o, {}).get('fuente') or ''
    ruta = os.path.join(RAIZ, f)
    if f.endswith('.json'):
        try:
            d = json.load(open(ruta, encoding='utf-8'))
            cuerpo = ' '.join(c.get('body') or '' for c in d.get('chapters') or [])
            return re.sub(r'<[^>]+>', '', re.sub(r'(?i)<br\s*/?>|</p>|</div>', '\n', html.unescape(cuerpo)))
        except Exception:
            return ''
    try:
        return re.sub(r'<<<PAGE \d+>>>', '\n', open(ruta, encoding='utf-8').read())
    except Exception:
        return ''


obras = {}
verso_de = {}
for o in OBRAS:
    t = texto_original(o)
    lineas = [x for x in t.split('\n') if len(x.split()) >= 1]
    cortas = sum(1 for x in lineas if len(x.split()) <= 8) / max(1, len(lineas))
    largas = sum(1 for x in lineas if len(x.split()) >= 12) / max(1, len(lineas))
    est = 'verso' if cortas >= 0.6 and largas < 0.2 else 'prosa' if cortas < 0.35 else 'mixto'
    verso_de[o] = est
    m = META.get(o, {}); f = FECHAS.get(o) or {}
    obras[o] = {'titulo': m.get('titulo', o), 'tipo': m.get('tipo_nodo'), 'pdf': m.get('archivo_pdf'), 'paginas': m.get('paginas'),
                'fuente_texto': m.get('fuente'), 'publicado': bool(m.get('publicado')),
                'fecha': f.get('punto'), 'fecha_fuente': f.get('fuente'), 'fecha_confianza': f.get('confianza'),
                'carpeta': f.get('carpeta'), 'palabras_contenido': sum(1 for x in seqs[o] if x),
                'verso_prosa_estimado': est, 'lineas_cortas': round(cortas, 2), 'lineas_largas': round(largas, 2)}

# ── familias ──
PRUEBA = [x for x in os.environ.get('FAMILIAS_PRUEBA', '').split(',') if x]
if PRUEBA:
    fam = {r: ms for r, ms in fam.items() if any(unidad(x) in ms for x in PRUEBA)}

# ── 1ª pasada: medir todos los pares; calibrar con las flexiones ──
def medibles(ms):
    return sorted((l for l in ms if l in objetivo), key=lambda l: -frec[l])[:10]  # se comparan los 10 más usados


for n_fam, (r, ms) in enumerate(fam.items()):
    if n_fam % 200 == 0:
        print('midiendo familia', n_fam, 'de', len(fam), file=sys.stderr, flush=True)
    med = medibles(ms)
    for i in range(len(med)):
        for j in range(i + 1, len(med)):
            comparar_cache(med[i], med[j])
ref = sorted(c['r'] for (a, b), c in _CMP.items() if c.get('r') is not None and es_flexion(a, b))
if len(ref) >= 20:
    UNE = ref[len(ref) // 4]          # se parecen al menos como el cuartil bajo de las flexiones
    SEPARA = ref[len(ref) // 20]      # y separa lo que queda claramente por debajo de casi todas
print('referencia de flexiones:', len(ref), 'pares · mediana', ref[len(ref) // 2] if ref else None,
      '· une ≥', UNE, '· separa: techo <', SEPARA, file=sys.stderr, flush=True)

salida, filas = [], []
for n_fam, (r, ms) in enumerate(fam.items()):
    if n_fam % 200 == 0:
        print('familia', n_fam, 'de', len(fam), file=sys.stderr, flush=True)
    med = medibles(ms)
    pares = []
    for i in range(len(med)):
        for j in range(i + 1, len(med)):
            c = comparar_cache(med[i], med[j])
            c['veredicto'] = veredicto(c)
            c['distribucion'] = distribucion(med[i], med[j])
            pares.append(dict(c, a=med[i], b=med[j], flexion=es_flexion(med[i], med[j])))
    # subfamilias de uso, por enlace promedio: dos grupos se juntan si el
    # parecido medio entre sus miembros medidos llega a «une» y ningún par
    # entre ellos «se separa» (sin esto, A~B y B~C juntaban A con C).
    R = {(pp['a'], pp['b']): pp for pp in pares}
    R.update({(pp['b'], pp['a']): pp for pp in pares})
    grupos = [[l] for l in med]
    while True:
        mejor = None
        for x in range(len(grupos)):
            for y in range(x + 1, len(grupos)):
                ps = [R[(a, b)] for a in grupos[x] for b in grupos[y] if (a, b) in R]
                rs_ = [q['r'] for q in ps if q.get('r') is not None]
                if not rs_ or any(q['veredicto'] == 'el uso separa' for q in ps):
                    continue
                m_ = sum(rs_) / len(rs_)
                if m_ >= UNE and (mejor is None or m_ > mejor[0]):
                    mejor = (m_, x, y)
        if not mejor:
            break
        _, x, y = mejor
        grupos[x] += grupos[y]
        del grupos[y]
    sub = sorted(grupos, key=lambda g: -sum(frec[l] for l in g))
    sub_de = {l: n + 1 for n, g in enumerate(sub) for l in g}
    separa = sum(1 for pp in pares if pp['veredicto'] == 'el uso separa')
    miembros = []
    for l in sorted(ms, key=lambda l: -frec[l]):
        os_ = obras_de[l]
        vv = collections.Counter(verso_de.get(o) for o in os_)
        miembros.append({'lema': l, 'forma': ver(l), 'formas': [f for f, _ in formas[l].most_common(6)], 'frec': frec[l],
                         'obras': len(os_), 'primera': min((anio(o) for o in os_ if anio(o)), default=None),
                         'en_verso': vv.get('verso', 0), 'en_prosa': vv.get('prosa', 0),
                         'medible': l in objetivo, 'subfamilia_uso': sub_de.get(l),
                         'fijado_por_la_autora': any(norm(k) != l and norm(v) == l for k, v in FORMAS_AUTORA.items()),
                         'vecinos': vecinos(l), 'ejemplos': ejemplo(l) if l in objetivo else []})
    une = sum(1 for pp in pares if pp['veredicto'] == 'une')
    # interés: familias con excepciones (parte une y parte separa), y con uso
    salida.append({'raiz': r, 'miembros': miembros, 'pares': pares, 'subfamilias_uso': [[ver(l) for l in g] for g in sub],
                   'separa': separa, 'une': une, 'frec': sum(frec[l] for l in ms),
                   'interes': round((min(une, separa) * 3 + separa + une) * math.log1p(sum(frec[l] for l in med)), 2)})
    for m in miembros:
        filas.append({'raiz': r, 'lema': m['lema'], 'forma': m['forma'], 'formas': ' '.join(m['formas']), 'frec': m['frec'],
                      'obras': m['obras'], 'primera': m['primera'] or '', 'subfamilia_uso': m['subfamilia_uso'] or '',
                      'n_subfamilias': len(sub), 'separa_en_familia': separa, 'vecinos': ' '.join(m['vecinos']),
                      'decision_autora': '', 'nota': ''})
salida.sort(key=lambda f: -f['interes'])
orden = {f['raiz']: n for n, f in enumerate(salida)}
filas.sort(key=lambda x: (orden[x['raiz']], -x['frec']))

meta = {'descripcion': 'Tanda 1 de pulenta: familias de lemas con excepciones. La raíz propone; el uso (vecinos ±%d en vectores de palabras, '
                       'sin la propia familia) decide en %d particiones del cuerpo en mitades por obra.' % (VENT, N_PARTES),
        'referencia': {'pares_de_flexion': len(ref), 'mediana': ref[len(ref) // 2] if ref else None,
                       'q25': ref[len(ref) // 4] if ref else None, 'q05': ref[len(ref) // 20] if ref else None},
        'espacio': 'vectores de palabras de la fase 2 (anexo, E.npy): cada aparición = media de sus vecinos, centrada',
        'umbrales': {'medida': 'coseno cruzado / raíz(autoparecido a · autoparecido b), entre mitades al azar de las apariciones, '
                               'solo en las obras donde aparecen los dos',
                     'une': 'r ≥ %.2f' % UNE, 'separa': 'techo de r < %.2f' % SEPARA, 'minimo_apariciones': MINF},
        'cuerpo': {'obras': len(OBRAS), 'palabras_contenido': sum(frec.values()), 'lemas': len(frec)},
        'familias': len(salida),
        'pares': collections.Counter(pp['veredicto'] for f in salida for pp in f['pares'])}
json.dump({'meta': meta, 'familias': salida}, open(os.path.join(SALIDA, 'familias.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
with open(os.path.join(SALIDA, 'familias-revision.csv'), 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
    w.writeheader(); w.writerows(filas)
json.dump({'descripcion': 'Una ficha por obra para pulenta: fecha (con su fuente y confianza), carpeta, PDF, texto, '
                          'y verso/prosa estimado por el largo de las líneas (a confirmar por la autora).', 'obras': obras},
          open(os.path.join(SALIDA, 'obras.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False))
if PRUEBA:
    for f in salida:
        for pp in f['pares']:
            print(' ', ver(pp['a']), '~', ver(pp['b']), pp['veredicto'], pp.get('r'), pp.get('r_techo'), pp.get('propio_a'), pp.get('propio_b'))
for f in salida[:15]:
    print(f['raiz'], '|', ' / '.join(f['subfamilias_uso'][0][:4]), '…' if len(f['subfamilias_uso']) > 1 else '',
          '| subfamilias', [g[:3] for g in f['subfamilias_uso']][:4], '| separa', f['separa'])
