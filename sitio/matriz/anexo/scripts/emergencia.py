"""Fase 6 · emergencia: conceptos, operadores, diagonales e instrumentos que
salen del cuerpo por correspondencia estructural, sin semillas.

Ninguna lista de la autora entra en el cálculo (ni diagonales, ni
instrumentos, ni núcleos, ni palabras marcadas). Se usan solo el texto, la
lematización de la página y el espacio estructural de la fase 2 (E.npy,
PPMI + SVD), que también se armó sin semillas. Las listas de la autora se
cruzan al final, solo para marcar coincidencias.

  conceptos     lemas que funcionan como concepto: mismo papel en obras
                distintas (contexto estable entre obras), familia
                derivativa propia (el cuerpo los conjuga), lugar de
                argumento (lo X, el X de), y no son vocabulario de base
  operadores    esqueletos de palabras de función con huecos (X) que el
                cuerpo repite más de lo que daría el azar: se comparan con
                el mismo texto barajado dentro de cada pasaje
  diagonales    pares de pasajes de obras distintas que se corresponden en
                el espacio estructural pero casi no comparten palabras
  instrumentos  un concepto atado a un operador en varias obras: la misma
                operación aplicada al mismo término

Escribe emergencia.json (intermedio) y lo exporta exportar.py.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
from fechas_base import anio_obra
import json, math, re, random, pickle, collections
import numpy as np
from lematica import tokens, norm, VACIAS, EXTRA
from clusters_base import GENERICAS
import criterios_base as cb

random.seed(7)
np.random.seed(7)
CORP = pickle.load(open('corpus.pkl', 'rb'))
EST = json.load(open('estructural.json'))
FECHAS = json.load(open('fechas.json'))
META = CORP['meta']
VOC = EST['voc']; VID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy').astype(np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9


def anio(o):
    return anio_obra(FECHAS, o)


_FUN_ES = set('de la que el en y a los se no las un por con una su para es lo como del al pero más sin'.split())


def es_castellano(t):
    """Por pasaje (hay obras en castellano con pasajes en inglés o francés):
    al menos un 18 % de palabras de función del castellano."""
    ws = re.findall(r"[^\W\d_]+", t.lower())
    return cb.idioma(t) == 'es' and sum(w in _FUN_ES for w in ws) >= 0.18 * max(1, len(ws))


DOCS = [d for d in CORP['docs'] if es_castellano(d['texto'])]
print(len(DOCS), 'pasajes en castellano', flush=True)
OBRAS = sorted({d['obra'] for d in DOCS})

# ── frecuencias ──
frec = collections.Counter(); df = collections.Counter(); obras_de = collections.defaultdict(collections.Counter)
for d in DOCS:
    ks = [c if c == 'sí' else norm(c) for c in d['claves']]
    d['k'] = ks
    frec.update(ks)
    for c in set(ks):
        df[c] += 1
    for c in ks:
        obras_de[c][d['obra']] += 1
N = len(DOCS)
idf = {c: math.log(N / n) for c, n in df.items()}
BASE = {c for c, o in obras_de.items() if len(o) >= len(OBRAS) / 2}   # vocabulario de base

# ══ 1. conceptos ══
CAND = [c for c in VID if frec[c] >= 8 and len(obras_de[c]) >= 3 and len(c) >= 4 and c not in GENERICAS
        and c not in VACIAS and c not in EXTRA]
print(len(CAND), 'candidatos a concepto', flush=True)

# contexto de cada aparición: media de E de las claves a ±6
ctx = collections.defaultdict(lambda: collections.defaultdict(list))
cand_set = set(CAND)
# un mismo verso o párrafo copiado en varias obras no prueba que el término
# funcione igual: se descartan las apariciones cuyo entorno (±4 claves) se repite
vent = collections.Counter()
for d in DOCS:
    ks = d['k']
    for j in range(len(ks)):
        vent[tuple(ks[max(0, j - 4):j + 5])] += 1
for d in DOCS:
    ks = d['k']; ids = [VID.get(c) for c in ks]
    for j, c in enumerate(ks):
        if c not in cand_set or vent[tuple(ks[max(0, j - 4):j + 5])] > 1:
            continue
        vec = [ids[x] for x in range(max(0, j - 6), min(len(ks), j + 7)) if x != j and ids[x] is not None and ks[x] != c]
        if len(vec) >= 3:
            ctx[c][d['obra']].append(E[vec].mean(0))


def estabilidad(c):
    cs = []
    for o, vs in ctx[c].items():
        if len(vs) >= 2:
            m = np.mean(vs, 0); cs.append(m / (np.linalg.norm(m) + 1e-9))
    if len(cs) < 3:
        return None
    M = np.array(cs); S = M @ M.T
    n = len(cs)
    return float((S.sum() - n) / (n * (n - 1)))


# familia derivativa: claves del cuerpo con la misma raíz (6 letras), que el
# cuerpo usa en al menos 2 obras
RAIZ6 = collections.defaultdict(set)
for c in frec:
    if len(c) >= 6 and frec[c] >= 2:
        RAIZ6[c[:6]].add(c)


def familia(c):
    return sorted(x for x in RAIZ6.get(c[:6], ()) if len(obras_de[x]) >= 2) if len(c) >= 6 else [c]


# lugar de argumento: «lo X», «el/la X de», «del X», «su X»: X nombrado como término
ARG = collections.Counter(); TOT = collections.Counter()
rx_arg = re.compile(r"\b(lo|el|la|del|al|su|un|una)\s+([^\W\d_]+)\s+(de|que|es|en|como|y|,|\.|;|:)", re.I)
forma_a_clave = {}
for d in DOCS:
    for m in rx_arg.finditer(d['texto']):
        w = m.group(2)
        k = forma_a_clave.get(w)
        if k is None:
            tk = tokens(w); k = forma_a_clave[w] = (tk[0][1] if tk else '')
            k = forma_a_clave[w] = (k if k == 'sí' else norm(k)) if k else ''
        if k in cand_set:
            ARG[k] += 1
for c in CAND:
    TOT[c] = frec[c]

filas = []
for c in CAND:
    est = estabilidad(c)
    if est is None:
        continue
    fam = familia(c)
    filas.append({'clave': c, 'estabilidad': est, 'familia': fam, 'n_familia': len(fam), 'argumento': ARG[c] / TOT[c],
                  'especificidad': idf[c], 'base': c in BASE, 'obras': len(obras_de[c]), 'n': frec[c]})


def z(xs):
    """Rango normalizado (0 a 1): ninguna medida pesa más por tener la
    distribución más estirada."""
    orden = np.argsort(np.argsort(xs))
    return list(orden / max(1, len(xs) - 1))


for k, zk in (('estabilidad', 'z_est'), ('argumento', 'z_arg'), ('especificidad', 'z_esp')):
    for f, v in zip(filas, z([f[k] for f in filas])):
        f[zk] = v
for f, v in zip(filas, z([math.log(f['n_familia']) for f in filas])):
    f['z_fam'] = v
for f in filas:
    # concepto: estable entre obras, conjugado, nombrado como término, no de base
    f['puntaje0'] = f['z_est'] + f['z_fam'] + f['z_arg'] + 0.5 * f['z_esp'] - (1.0 if f['base'] else 0)

# ══ 2. operadores ══
PAL = re.compile(r"[^\W\d_]+", re.U)
todas = collections.Counter()
for d in DOCS:
    todas.update(w.lower() for w in PAL.findall(d['texto']))
FUNC = {w for w, _ in todas.most_common(110)}          # las más frecuentes del cuerpo, no una lista dada
FUNC -= {w for w in FUNC if len(w) > 7}


def esqueleto(ws):
    return tuple(w if w in FUNC else 'X' for w in ws)


def contar(seqs):
    C = collections.Counter(); O = collections.defaultdict(set)
    for o, ws in seqs:
        sk = esqueleto(ws)
        for n in (3, 4, 5):
            for i in range(len(sk) - n + 1):
                g = sk[i:i + n]
                nx = g.count('X'); nf = n - nx
                if nx < 1 or nf < 2 or g[0] == 'X' and g[-1] == 'X' and nx == n - 1:
                    continue
                if nx > 2:
                    continue
                C[g] += 1; O[g].add(o)
    return C, O


seqs = [(d['obra'], [w.lower() for w in PAL.findall(d['texto'])]) for d in DOCS]
C, O = contar(seqs)
# línea de base: lo que darían los pares de palabras vecinas solos (cadena de
# Markov de orden 1 sobre los esqueletos). Lo que la supera es construcción de
# más largo alcance, no sintaxis local.
U = collections.Counter(); BI = collections.Counter()
for o, ws in seqs:
    sk = esqueleto(ws)
    U.update(sk); BI.update(zip(sk, sk[1:]))


def esperado(g):
    e = BI[(g[0], g[1])]
    for a, b in zip(g[1:], g[2:]):
        e *= BI[(a, b)] / max(1, U[a])
    return e


OPS = []
for g, c in C.items():
    if c < 12 or len(O[g]) < 6:
        continue
    lift = c / max(esperado(g), 1e-9)
    if lift < 2.5:
        continue
    OPS.append({'patron': ' '.join(g), 'n': c, 'obras': len(O[g]), 'lift': round(lift, 1), 'puntaje': math.log(lift) * math.log(c)})
OPS.sort(key=lambda x: -x['puntaje'])
# forma canónica: sin los huecos de los bordes. Si adentro queda un hueco es
# una construcción («ni X ni X»); si no, un conector («si y sólo si»). Las
# frases hechas sin hueco que no conectan (de vez en cuando) quedan como
# conector igual: el cuerpo decide, no una lista.
canon = {}
for op in OPS:
    t = op['patron'].split()
    while t and t[0] == 'X':
        t = t[1:]
    while t and t[-1] == 'X':
        t = t[:-1]
    op['canon'] = ' '.join(t); op['tipo'] = 'construcción' if 'X' in t else 'conector'
    if len(t) < 2:
        continue
    if op['canon'] not in canon or canon[op['canon']]['puntaje'] < op['puntaje']:
        canon[op['canon']] = op
OPS = sorted(canon.values(), key=lambda x: -x['puntaje'])
# fuera los que son parte de otro más largo con casi la misma cuenta
mantener = []
for op in OPS:
    if any(op['canon'] in m['canon'] and m['n'] >= 0.7 * op['n'] for m in mantener):
        continue
    mantener.append(op)
OPERADORES = mantener[:40]
print('operadores:', ' | '.join(o['patron'] for o in OPERADORES[:25]), flush=True)

# huecos: cuántas veces cada candidato ocupa la X de un operador, en cuántas obras
clave_de_forma = {}


def clave_forma(w):
    if w not in clave_de_forma:
        tk = tokens(w)
        k = tk[0][1] if tk else ''
        clave_de_forma[w] = (k if k == 'sí' else norm(k)) if k else ''
    return clave_de_forma[w]


pat_ops = [(o['patron'], tuple(o['patron'].split())) for o in OPERADORES if o['tipo'] == 'construcción']
hueco = collections.Counter(); hueco_obras = collections.defaultdict(set)
for o, ws in seqs:
    sk = esqueleto(ws)
    for nombre, p in pat_ops:
        n = len(p)
        for i in range(len(sk) - n + 1):
            if sk[i:i + n] == p:
                for j, t in enumerate(p):
                    if t == 'X':
                        c = clave_forma(ws[i + j])
                        if c in cand_set:
                            hueco[c] += 1; hueco_obras[c].add(o)
# Registros de operadores: el contexto de cada operador (media de E de las
# claves a ±8) separa los operadores en dos grupos (k-medias, k=2). No se
# elige cuál vale: cada registro tiene sus conceptos.
todos_ops = [tuple(o['canon'].split()) for o in OPERADORES]
ctx_op = [[] for _ in OPERADORES]
apar = []  # (pasaje, posición, largo, operador)
for di, (o, ws) in enumerate(seqs):
    sk = esqueleto(ws)
    for k, p in enumerate(todos_ops):
        n = len(p)
        for i in range(len(sk) - n + 1):
            if sk[i] == p[0] and sk[i:i + n] == p:
                apar.append((di, i, n, k))
                if len(ctx_op[k]) < 400:
                    ids = [VID.get(clave_forma(w)) for w in ws[max(0, i - 8):i + n + 8]]
                    ids = [x for x in ids if x is not None]
                    if ids:
                        ctx_op[k].append(E[ids].mean(0))
C_op = np.array([np.mean(v, 0) if v else np.zeros(E.shape[1]) for v in ctx_op], dtype=np.float32)
C_op /= np.linalg.norm(C_op, axis=1, keepdims=True) + 1e-9
cen = C_op[[0, int(np.argmin(C_op @ C_op[0]))]].copy()
for _ in range(50):
    lab = np.argmax(C_op @ cen.T, axis=1)
    nuevo = np.array([C_op[lab == g].mean(0) if (lab == g).any() else cen[g] for g in (0, 1)])
    nuevo /= np.linalg.norm(nuevo, axis=1, keepdims=True) + 1e-9
    if np.allclose(nuevo, cen):
        break
    cen = nuevo
for op, g in zip(OPERADORES, lab):
    op['registro'] = int(g)
cerca = [collections.Counter(), collections.Counter()]; cubiertas = [0, 0]; total_w = sum(len(ws) for _, ws in seqs)
por_pasaje = collections.defaultdict(list)
for di, i, n, k in apar:
    por_pasaje[di].append((i, n, int(lab[k])))
for di, lst in por_pasaje.items():
    ws = seqs[di][1]
    for g in (0, 1):
        marca = bytearray(len(ws))
        for i, n, gg in lst:
            if gg == g:
                for x in range(max(0, i - 8), min(len(ws), i + n + 8)):
                    marca[x] = 1
        cubiertas[g] += sum(marca)
        for x, w in enumerate(ws):
            if marca[x]:
                c = clave_forma(w)
                if c in cand_set:
                    cerca[g][c] += 1
base_op = [cubiertas[g] / max(1, total_w) for g in (0, 1)]
print('línea de base por registro', [round(b, 3) for b in base_op], flush=True)
for f in filas:
    f['hueco'] = hueco[f['clave']] / f['n']; f['hueco_obras'] = len(hueco_obras[f['clave']])
    # suavizado hacia la base (20 apariciones de peso): una palabra rara no
    # se destaca por dos casualidades
    f['operado_reg'] = [((cerca[g][f['clave']] + 20 * base_op[g]) / (f['n'] + 20)) / base_op[g] for g in (0, 1)]
    f['registro'] = int(np.argmax(f['operado_reg']))
    f['operado'] = max(f['operado_reg'])
for f, v in zip(filas, z([math.log(f['operado'] + 0.05) for f in filas])):
    f['z_hueco'] = v
for f in filas:
    # concepto: estable entre obras, operado (en el hueco de los operadores),
    # conjugado, nombrado como término, no vocabulario de base
    f['puntaje'] = 0.8 * f['z_est'] + f['z_fam'] + 0.6 * f['z_arg'] + 0.4 * f['z_esp'] + 2 * f['z_hueco'] - (1.0 if f['base'] else 0)
filas.sort(key=lambda f: -f['puntaje'])
CONCEPTOS = []
for g in (0, 1):
    vistos = set(); lista = []
    for f in filas:
        r = f['clave'][:6] if len(f['clave']) >= 6 else f['clave']
        # término nombrado (lo X, el X de…) en al menos una de cada cinco
        # apariciones, y operado más de lo que daría el azar en este registro
        if r in vistos or f['argumento'] < 0.2 or f['registro'] != g or f['operado'] <= 1.0:
            continue
        vistos.add(r); lista.append(f)
    CONCEPTOS += lista[:30]
    print('registro', g, 'operadores:', ' | '.join(o['canon'] for o in OPERADORES if o['registro'] == g))
    print('  conceptos:', ', '.join(f['clave'] for f in lista[:30]), flush=True)

# ══ 4. instrumentos: un concepto atado a un operador en varias obras ══
# Atadura = cuántas veces el concepto cae dentro de la ventana (±8 palabras)
# de ese operador, contra lo esperable por la frecuencia del concepto y lo que
# cubre el operador. Es la misma operación aplicada al mismo término.
conc_set = {f['clave'] for f in CONCEPTOS}
fam_de = {}
for f in CONCEPTOS:
    for x in f['familia']:
        fam_de.setdefault(x, f['clave'])
fam_de.update({f['clave']: f['clave'] for f in CONCEPTOS})
cubre = collections.Counter()
ligas = collections.defaultdict(lambda: {'n': 0, 'obras': set(), 'ej': []})
for di, i, n, k in apar:
    o, ws = seqs[di]
    a, b = max(0, i - 8), min(len(ws), i + n + 8)
    cubre[k] += b - a
    vistos_ = set()
    for x in range(a, b):
        c = fam_de.get(clave_forma(ws[x]))
        if c and c not in vistos_:
            vistos_.add(c)
            L = ligas[(c, k)]
            L['n'] += 1; L['obras'].add(o)
            if len(L['ej']) < 3:
                L['ej'].append({'obra': o, 'texto': ' '.join(ws[a:b])})
INSTR = []
for (c, k), L in ligas.items():
    if len(L['obras']) < 3 or L['n'] < 4:
        continue
    esperado_ = frec[c] * cubre[k] / max(1, total_w)
    atadura = L['n'] / max(esperado_, 1e-6)
    if atadura < 2:
        continue
    op = OPERADORES[k]
    INSTR.append({'concepto': c, 'operador': op['canon'], 'registro': op['registro'], 'n': L['n'], 'obras': sorted(L['obras']),
                  'atadura': round(atadura, 1), 'ejemplos': L['ej']})
INSTR.sort(key=lambda x: -(len(x['obras']) * math.log(x['atadura'])))
INSTR = INSTR[:40]
print('instrumentos:', ' | '.join(f"{i['concepto']} ~ {i['operador']} ({len(i['obras'])} obras, x{i['atadura']})" for i in INSTR[:20]), flush=True)

# ══ 3. diagonales: correspondencia estructural sin léxico compartido ══
# claves de otra lengua: las que el cuerpo usa sobre todo en pasajes que no
# están en castellano (quedan afuera del vector aunque el pasaje sea mixto)
en_es = collections.Counter(); en_otra = collections.Counter()
for d in CORP['docs']:
    ks = [c if c == 'sí' else norm(c) for c in d['claves']]
    (en_es if es_castellano(d['texto']) else en_otra).update(ks)
AJENAS = {c for c in en_otra if en_otra[c] > en_es[c]}
print(len(AJENAS), 'claves de otra lengua', flush=True)
voc_ok = [c for c in VID if c not in GENERICAS and c not in VACIAS and c not in EXTRA and c not in AJENAS]
ok = set(voc_ok)
S_rows, L_rows, info = [], [], []
lex_ids = {c: i for i, c in enumerate(sorted(frec))}
for d in DOCS:
    tf = collections.Counter(c for c in d['k'] if c in ok)
    if sum(tf.values()) < 25:
        continue
    w = {c: (1 + math.log(n)) * idf[c] for c, n in tf.items()}
    v = sum(E[VID[c]] * x for c, x in w.items()); v /= np.linalg.norm(v) + 1e-9
    nl = math.sqrt(sum(x * x for x in w.values()))
    S_rows.append(v); L_rows.append({c: x / nl for c, x in w.items()}); info.append(d)
info_vec = None
S = np.array(S_rows, dtype=np.float32)
# todos los pasajes comparten una dirección común (el «tono» del cuerpo): se
# resta el centro y las 3 primeras componentes, para que la correspondencia
# sea de estructura y no de registro general
S -= S.mean(0)
_, _, Vt = np.linalg.svd(S[np.random.choice(len(S), min(4000, len(S)), replace=False)], full_matrices=False)
for k in range(3):
    S -= np.outer(S @ Vt[k], Vt[k])
S /= np.linalg.norm(S, axis=1, keepdims=True) + 1e-9
info_vec = np.array(S_rows, dtype=np.float32)   # vectores sin centrar, para leer las claves
print(len(S), 'pasajes con vector', flush=True)
fam_obra = {}  # familias de texto repetido (fase 1): Aire/Embriaguez/Lie Lay Ley
for a in ('aire-en-la-cuerda', 'de-embriaguez-y-pathos', 'lie-lay-ley'):
    fam_obra[a] = 'aire'
muestra = S[np.random.choice(len(S), 1500, replace=False)]
SS = muestra @ muestra.T
UMBRAL = float(np.quantile(SS[np.triu_indices(len(SS), 1)], 0.999))   # el 0,1 % más alto
print('umbral estructural', round(UMBRAL, 3), flush=True)
pares = []
for i0 in range(0, len(S), 600):
    B = S[i0:i0 + 600] @ S.T
    for r in range(B.shape[0]):
        i = i0 + r
        orden = np.argpartition(-B[r], 40)[:40]
        for j in orden:
            if j <= i:
                continue
            oi, oj = info[i]['obra'], info[j]['obra']
            if oi == oj or fam_obra.get(oi, oi) == fam_obra.get(oj, oj):
                continue
            s = float(B[r, j])
            if s < UMBRAL:
                continue
            Li, Lj = L_rows[i], L_rows[j]
            lex = sum(x * Lj.get(c, 0) for c, x in Li.items())
            if lex > 0.12:
                continue
            pares.append((s - lex, s, lex, i, j))
pares.sort(reverse=True)
print(len(pares), 'pares estructurales sin léxico compartido', flush=True)


def eje(i, j):
    """Las claves de cada lado que más aportan a la correspondencia, y la
    palabra del cuerpo más cercana a lo que comparten."""
    vi, vj = S[i], S[j]
    prod = (vi + vj) / 2
    def aporte(L, otro):
        return sorted(L, key=lambda c: -float(E[VID[c]] @ otro) * L[c])[:5]
    ai = aporte(L_rows[i], info_vec[j]); aj = aporte(L_rows[j], info_vec[i])
    # el eje: las claves de los dos pasajes que más se acercan a la vez a
    # ambos (están en uno y responden al otro)
    cand_eje = set(L_rows[i]) | set(L_rows[j])
    nombre = sorted(cand_eje, key=lambda c: -min(float(E[VID[c]] @ info_vec[i]), float(E[VID[c]] @ info_vec[j])))[:3]
    return ai, aj, nombre


usados = collections.Counter(); DIAG = []
cupo = {'largo': 25, 'cerca': 15}
for d_, s_, lex, i, j in pares:
    a, b = info[i], info[j]
    ta, tb = anio(a['obra']), anio(b['obra'])
    dist = abs(ta - tb) if ta and tb else None
    alcance = 'largo' if dist is not None and dist >= 3 else 'cerca'
    if cupo[alcance] <= 0:
        continue
    k = tuple(sorted((a['obra'], b['obra'])))
    if usados[k] >= 2 or usados[a['id']] or usados[b['id']]:
        continue
    usados[k] += 1; usados[a['id']] += 1; usados[b['id']] += 1; cupo[alcance] -= 1
    ai, aj, nombre = eje(i, j)
    DIAG.append({'a': {'id': a['id'], 'obra': a['obra'], 'anio': ta, 'claves': ai, 'texto': re.sub(r'\s+', ' ', a['texto'])[:420]},
                 'b': {'id': b['id'], 'obra': b['obra'], 'anio': tb, 'claves': aj, 'texto': re.sub(r'\s+', ' ', b['texto'])[:420]},
                 'estructural': round(s_, 3), 'lexico': round(lex, 3), 'eje': nombre, 'alcance': alcance,
                 'distancia': round(dist, 1) if dist is not None else None})
    if not any(cupo.values()):
        break
print('diagonales:', len(DIAG), flush=True)

# ── cruce con lo que la autora ya nombró (solo para marcar) ──
import sys, os
sys.path.insert(0, os.path.join(RAIZ, 'sitio', 'matriz'))
import comun  # noqa: E402
REG = json.load(open(os.path.join(RAIZ, 'sitio', 'matriz', 'instrumentos.json'))).get('instrumentos', [])
nombrados = set()
for it in (REG if isinstance(REG, list) else REG.values()):
    for w in [it.get('etiqueta') or '', it.get('lema') or '', it.get('id') or ''] + (it.get('alias') or []):
        for _, c in tokens(str(w).replace('-', ' ')):
            nombrados.add(c if c == 'sí' else norm(c))
for d in comun.diagonales_confirmadas():
    t = d.get('tipo') or {}
    for w in (t.get('lemas') or []) + [t.get('instrumento') or '', t.get('titulo') or '']:
        for _, c in tokens(str(w).replace('-', ' ')):
            nombrados.add(c if c == 'sí' else norm(c))
for f in CONCEPTOS:
    f['ya_nombrado'] = bool(set(f['familia']) & nombrados) or f['clave'] in nombrados
for i in INSTR:
    i['ya_nombrado'] = i['concepto'] in nombrados

json.dump({'filas': filas[:400], 'conceptos': CONCEPTOS, 'operadores': OPERADORES, 'instrumentos': INSTR, 'diagonales': DIAG,
           'funcion': sorted(FUNC), 'pasajes': len(DOCS)},
          open('emergencia.json', 'w'), ensure_ascii=False, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
print('listo')
