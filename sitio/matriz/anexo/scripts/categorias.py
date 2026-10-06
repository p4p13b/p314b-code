"""Fase 7 · categorías: las ~540 propuestas de la matriz (motor + lectura del
Cowork) reducidas a pocas categorías que salen del propio material, para
decidir por categoría y no caso por caso.

Qué se mide de cada propuesta (par de pasajes), sin usar lo que dice el
instrumento ni el tipo que trae:
  estructural   correspondencia en el espacio de la fase 2 (sin el tono común)
  léxico        palabras compartidas (tf-idf)
  raro          palabras raras compartidas (en ≤ 20 pasajes de todo el cuerpo)
  núcleo        si los dos lados cargan el mismo núcleo de la fase 2
  conceptos     conceptos de la fase 6 en común
  argumentativo operadores del registro argumentativo (fase 6), el menor de
                los dos lados
  anafórico     operadores del registro anafórico, el menor de los dos
  verso         cuánto de verso tienen los dos lados (cortes de línea)
  distancia     años entre las dos obras
  reescritura   mismo cuerpo de texto (familias de la fase 1 o léxico muy alto)

Las categorías salen de agrupar esos perfiles (k-medias, k elegido por
silueta). Cada una se define por lo que la distingue del resto, con peso
(cuántas propuestas, cuántas obras, cohesión) y evidencia (casos tipo).

Además:
  instrumentos  si los 40 casos de cada instrumento de la autora se parecen
                entre sí más que el azar, y cuánto se pisan entre ellos
  herramientas  procedimientos de escritura: los pasajes de todo el cuerpo
                agrupados por su forma (verso, cortes, repetición, notación,
                neologismo, operadores)
  conceptos     fase 6 + núcleos de la fase 2, con su peso
  decisiones    dónde caen las 12 decisiones de la autora

Escribe categorias.json (intermedio); lo exporta exportar.py.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
from fechas_base import anio_obra
import json, math, re, collections, os, random
import numpy as np
from lematica import tokens, norm, VACIAS, EXTRA
from clusters_base import GENERICAS

random.seed(11); np.random.seed(11)
M = os.path.join(RAIZ, 'sitio', 'matriz')
PAS = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))['pasajes']
EST = json.load(open('estructural.json'))
CONS = json.load(open('consenso.json'))
EM = json.load(open('emergencia.json'))
FECHAS = json.load(open('fechas.json'))
VOC = EST['voc']; VID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy').astype(np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
PROP = json.load(open(os.path.join(M, 'propuestas.json')))['propuestas']
COW = json.load(open(os.path.join(M, 'propuestas-cowork.json')))['propuestas']
DEC = json.load(open(os.path.join(M, 'decisiones.json')))['decisiones']
INSTR = json.load(open(os.path.join(M, 'instrumentos.json')))['instrumentos']
FAMILIA = {'aire-en-la-cuerda': 'aire', 'de-embriaguez-y-pathos': 'aire', 'lie-lay-ley': 'aire'}


def anio(o):
    return anio_obra(FECHAS, o)


# ── pasajes: claves y vectores ──
por_id = {p['id']: p for p in PAS}
por_sitio = collections.defaultdict(list)
for p in PAS:
    por_sitio[p['sitio']].append(p)
CLAVES = {}
df = collections.Counter()
for p in PAS:
    ks = [c if c == 'sí' else norm(c) for _, c in tokens(p['texto'])]
    CLAVES[p['id']] = ks
    df.update(set(ks))
N = len(PAS)
idf = {c: math.log(N / n) for c, n in df.items()}
OK = {c for c in VID if c not in GENERICAS and c not in VACIAS and c not in EXTRA}


def vectores(pid):
    tf = collections.Counter(c for c in CLAVES[pid] if c in OK)
    if not tf:
        return None, {}
    w = {c: (1 + math.log(n)) * idf[c] for c, n in tf.items()}
    v = sum(E[VID[c]] * x for c, x in w.items())
    nl = math.sqrt(sum(x * x for x in w.values()))
    return v / (np.linalg.norm(v) + 1e-9), {c: x / nl for c, x in w.items()}


# centro y componentes comunes del cuerpo (como en la fase 6)
muestra = random.sample(PAS, 3000)
Vm = np.array([v for v in (vectores(p['id'])[0] for p in muestra) if v is not None])
CENTRO = Vm.mean(0)
_, _, Vt = np.linalg.svd(Vm - CENTRO, full_matrices=False)
PCS = Vt[:3]


def estructura(v):
    v = v - CENTRO
    for k in range(3):
        v = v - (v @ PCS[k]) * PCS[k]
    return v / (np.linalg.norm(v) + 1e-9)


NUC = [set(n['miembros']) for n in CONS['nucleos']]
NUC_NOM = [n['palabra'] for n in CONS['nucleos']]
CONC = {}
for f in EM['conceptos']:
    for x in f['familia'] + [f['clave']]:
        CONC.setdefault(x, f['clave'])
OPS = [(o['canon'], o['registro']) for o in EM['operadores']]
REG_ARG = (next((o['registro'] for o in EM['operadores'] if re.search('sólo si|por lo tanto|es decir', o['canon'])), 1))
PAL = re.compile(r"[^\W\d_]+", re.U)


def perfil(pid):
    p = por_id[pid]; t = p['texto']
    v, L = vectores(pid)
    ks = CLAVES[pid]
    ws = [w.lower() for w in PAL.findall(t)]
    nw = max(1, len(ws))
    sk = ' '.join(ws)
    reg = [0, 0]
    for canon, g in OPS:
        patron = r'\b' + r'\s+'.join(r'\w+' if x == 'X' else re.escape(x) for x in canon.split()) + r'\b'
        reg[g] += len(re.findall(patron, sk))
    lineas = [l for l in t.split('\n') if l.strip()]
    corto = sum(1 for l in lineas if len(l.split()) <= 8) / max(1, len(lineas))
    nucleo = np.array([sum(1 for c in ks if c in n) for n in NUC], dtype=float)
    return {'v': estructura(v) if v is not None else None, 'L': L, 'ks': set(ks),
            'conc': {CONC[c] for c in ks if c in CONC}, 'nucleo': nucleo,
            'arg': 100 * reg[REG_ARG] / nw, 'ana': 100 * reg[1 - REG_ARG] / nw,
            'verso': corto, 'obra': p.get('obra_clave') or p['sitio'], 'texto': t}


# ── propuestas → pasajes ──
def limpio(s):
    return re.sub(r'\s+', ' ', re.sub(r'[…]', ' ', s or '')).strip()


def letras(s):
    return re.sub(r'[^a-z0-9ñ]+', '', norm(s or ''))


LETRAS = {}


def ubicar(lado):
    if lado.get('pasaje') in por_id:
        return lado['pasaje']
    cita = limpio(lado.get('cita'))
    trozos = [x for x in cita.split('  ') if len(x) > 20] or [cita]
    cand = por_sitio.get(lado.get('sitio'), [])
    if lado.get('pdf_pagina') is not None:
        pid = 'pdf:%s:p%s' % (lado['sitio'], lado['pdf_pagina'])
        if pid in por_id:
            return pid
    for p in cand:
        tx = re.sub(r'\s+', ' ', p['texto'])
        if any(tr[:60] in tx for tr in trozos if tr):
            return p['id']
    # sin espacios, guiones ni tildes (las citas del Cowork cortan y unen líneas)
    clave_ = letras(cita)
    for largo in (60, 35):
        for ini in (0, len(clave_) // 3):
            tr = clave_[ini:ini + largo]
            if len(tr) < 25:
                continue
            for p in cand:
                if p['id'] not in LETRAS:
                    LETRAS[p['id']] = letras(p['texto'])
                if tr in LETRAS[p['id']]:
                    return p['id']
    return None


CASOS = []
for p in PROP:
    CASOS.append({'id': p['id'], 'fuente': 'motor', 'instrumento': p.get('instrumento'), 'tipo': None,
                  'a': ubicar(p['origen']), 'b': ubicar(p['destino']), 'o': p['origen'], 'd': p['destino']})
for p in COW:
    CASOS.append({'id': p['id'], 'fuente': 'cowork', 'instrumento': None, 'tipo': p.get('tipo'),
                  'a': ubicar(p['origen']), 'b': ubicar(p['destino']), 'o': p['origen'], 'd': p['destino']})
ubicados = [c for c in CASOS if c['a'] and c['b']]
print(len(CASOS), 'propuestas;', len(ubicados), 'con sus dos pasajes ubicados', flush=True)

PERF = {}
for c in ubicados:
    for pid in (c['a'], c['b']):
        if pid not in PERF:
            PERF[pid] = perfil(pid)

RARAS = {c for c, n in df.items() if n <= 20}


def rasgos(a, b):
    """Señales del par (pasaje a, pasaje b)."""
    A, B = PERF[a], PERF[b]
    est = float(A['v'] @ B['v']) if A['v'] is not None and B['v'] is not None else 0.0
    lex = sum(x * B['L'].get(k, 0) for k, x in A['L'].items())
    na, nb = A['nucleo'], B['nucleo']
    ta, tb = anio(A['obra']), anio(B['obra'])
    return {'estructura': est, 'vocabulario': lex, 'raras': len(A['ks'] & B['ks'] & RARAS),
            'núcleo': float(na @ nb / (np.linalg.norm(na) * np.linalg.norm(nb))) if na.any() and nb.any() else 0.0,
            'conceptos': len(A['conc'] & B['conc']), 'argumentativo': min(A['arg'], B['arg']),
            'anafórico': min(A['ana'], B['ana']), 'verso': min(A['verso'], B['verso']),
            'reescritura': 1.0 if FAMILIA.get(A['obra'], A['obra']) == FAMILIA.get(B['obra'], B['obra']) or lex > 0.35 else 0.0,
            'distancia': abs(ta - tb) if ta and tb else None}


SENALES = ['estructura', 'vocabulario', 'raras', 'núcleo', 'conceptos', 'argumentativo', 'anafórico', 'verso']

# ── línea de base: pares de pasajes al azar, de obras distintas ──
# Una señal «sostiene» una relación solo si supera lo que da el azar en el
# mismo cuerpo (percentil 90 de 3000 pares al azar).
pool = [p['id'] for p in PAS if len(CLAVES[p['id']]) >= 25]
BASE = {k: [] for k in SENALES}
hechos = 0
while hechos < 3000:
    a, b = random.sample(pool, 2)
    if por_id[a].get('obra_clave') == por_id[b].get('obra_clave'):
        continue
    for pid in (a, b):
        if pid not in PERF:
            PERF[pid] = perfil(pid)
    r = rasgos(a, b)
    for k in SENALES:
        BASE[k].append(r[k])
    hechos += 1
BASE = {k: np.sort(np.array(v)) for k, v in BASE.items()}


def percentil(k, x):
    return float(np.searchsorted(BASE[k], x, side='right') / len(BASE[k]))


TIPOS = {
    'reescritura': 'El mismo cuerpo de texto, reescrito o copiado entre obras (familia de la fase 1 o vocabulario casi idéntico). No es una relación entre ideas: es una versión.',
    'eco de palabra rara': 'Comparten palabras raras del cuerpo (que aparecen en 20 pasajes o menos de todo el corpus): un término propio que vuelve en otro lugar.',
    'vocabulario compartido': 'Comparten vocabulario bastante más que dos pasajes cualesquiera del cuerpo.',
    'correspondencia estructural': 'Se corresponden en el espacio estructural (fase 2) una vez restado el tono común: arman la misma configuración aunque cambien las palabras.',
    'mismo núcleo': 'Los dos cargan el mismo núcleo conceptual de la fase 2 (diferir, existencia, realización, continuo, imposibilidad, eterno, modalidad…).',
    'concepto compartido': 'Comparten conceptos que el cuerpo opera como tales (fase 6).',
    'operación argumentativa': 'Los dos usan los operadores argumentativos del cuerpo (si y sólo si, a su vez, por lo tanto, es decir).',
    'operación anafórica': 'Los dos usan las construcciones anafóricas del cuerpo (ni… ni…, me… me…, cual si… fuera).',
    'misma forma (verso)': 'Los dos están en verso: la relación es de forma, no de contenido.',
    'sin sustento en el material': 'Ninguna señal supera lo que daría un par de pasajes al azar del mismo cuerpo. Candidata a descartarse en bloque.',
}
DE_SENAL = {'raras': 'eco de palabra rara', 'vocabulario': 'vocabulario compartido', 'estructura': 'correspondencia estructural',
            'núcleo': 'mismo núcleo', 'conceptos': 'concepto compartido', 'argumentativo': 'operación argumentativa',
            'anafórico': 'operación anafórica', 'verso': 'misma forma (verso)'}
# a igual fuerza, la señal más específica primero
PRIORIDAD = ['raras', 'conceptos', 'estructura', 'núcleo', 'argumentativo', 'anafórico', 'vocabulario', 'verso']


def clasificar(a, b):
    r = rasgos(a, b)
    pct = {k: percentil(k, r[k]) for k in SENALES}
    # una señal en cero no sostiene nada (p. ej. sin conceptos en común)
    presentes = [k for k in SENALES if pct[k] >= 0.9 and r[k] > 0]
    if r['reescritura']:
        tipo = 'reescritura'
    elif presentes:
        tipo = DE_SENAL[max(presentes, key=lambda k: (pct[k], -PRIORIDAD.index(k)))]
    else:
        tipo = 'sin sustento en el material'
    alcance = 'largo' if r['distancia'] is not None and r['distancia'] >= 3 else 'cercano'
    fuerza = max([pct[k] for k in presentes], default=0.0)
    return tipo, alcance, fuerza, presentes, r, pct


ASIG = {}
for c in ubicados:
    t, al, fz, pres, r, pct = clasificar(c['a'], c['b'])
    ASIG[c['id']] = {'tipo': t, 'alcance': al, 'fuerza': round(fz, 3), 'senales': pres,
                     'medidas': {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}}

CATS = []
for t, definicion in TIPOS.items():
    cs = [c for c in ubicados if ASIG[c['id']]['tipo'] == t]
    if not cs:
        continue
    obras = {PERF[c['a']]['obra'] for c in cs} | {PERF[c['b']]['obra'] for c in cs}
    cs_orden = sorted(cs, key=lambda c: -ASIG[c['id']]['fuerza'])
    conc = collections.Counter(x for c in cs for x in (PERF[c['a']]['conc'] & PERF[c['b']]['conc']))
    raras = collections.Counter(x for c in cs for x in (PERF[c['a']]['ks'] & PERF[c['b']]['ks'] & RARAS))
    CATS.append({'tipo': t, 'definicion': definicion, 'n': len(cs), 'obras': len(obras),
                 'largo_alcance': sum(1 for c in cs if ASIG[c['id']]['alcance'] == 'largo'),
                 'fuerza_media': round(float(np.mean([ASIG[c['id']]['fuerza'] for c in cs])), 3),
                 'fuentes': dict(collections.Counter(c['fuente'] for c in cs)),
                 'instrumentos': dict(collections.Counter(c['instrumento'] for c in cs if c['instrumento']).most_common()),
                 'tipos_cowork': dict(collections.Counter(c['tipo'] for c in cs if c['tipo']).most_common()),
                 'conceptos': [x for x, _ in conc.most_common(8)], 'palabras_raras': [x for x, _ in raras.most_common(10)],
                 'casos': [{'propuesta': c['id'], 'fuerza': ASIG[c['id']]['fuerza'], 'senales': ASIG[c['id']]['senales'],
                            'a': {'obra': PERF[c['a']]['obra'], 'texto': re.sub(r'\s+', ' ', PERF[c['a']]['texto'])[:260]},
                            'b': {'obra': PERF[c['b']]['obra'], 'texto': re.sub(r'\s+', ' ', PERF[c['b']]['texto'])[:260]}}
                           for c in cs_orden[:5]],
                 'propuestas': [c['id'] for c in cs_orden]})
CATS.sort(key=lambda x: (x['tipo'] == 'sin sustento en el material', -x['n']))
print()
for c in CATS:
    print(c['n'], c['tipo'], '| obras', c['obras'], '| largo', c['largo_alcance'], '| fuerza', c['fuerza_media'], '|', c['instrumentos'], c['tipos_cowork'], '|', c['conceptos'][:4], c['palabras_raras'][:5])

# ── instrumentos de la autora: ¿se sostienen en el material? ──
pares_azar = []
vs_pool = [PERF[k]['v'] for k in PERF if PERF[k]['v'] is not None]
for _ in range(4000):
    pares_azar.append(float(random.choice(vs_pool) @ random.choice(vs_pool)))
base_mu, base_sd = float(np.mean(pares_azar)), float(np.std(pares_azar))
grupos = collections.defaultdict(list)
for c in ubicados:
    if c['instrumento']:
        grupos[c['instrumento']].append(c)
cent, INS = {}, []
for ins, cs in grupos.items():
    vs = [PERF[p]['v'] for c in cs for p in (c['a'], c['b']) if PERF[p]['v'] is not None]
    M_ = np.array(vs); S_ = M_ @ M_.T; n = len(vs)
    coh = float((S_.sum() - n) / (n * (n - 1)))
    cent[ins] = M_.mean(0)
    tipos_ = collections.Counter(ASIG[c['id']]['tipo'] for c in cs)
    sin = tipos_.get('sin sustento en el material', 0) / len(cs)
    meta = next((x for x in INSTR if x['id'] == ins), {})
    INS.append({'instrumento': ins, 'etiqueta': meta.get('etiqueta') or ins, 'estatuto': meta.get('estatuto'),
                'n': len(cs), 'cohesion': round(coh, 3), 'z': round((coh - base_mu) / base_sd, 2),
                'sin_sustento': round(sin, 2), 'tipos': dict(tipos_.most_common())})
SOL = {}
for a in cent:
    for b in cent:
        if a < b:
            ca, cb = cent[a] / np.linalg.norm(cent[a]), cent[b] / np.linalg.norm(cent[b])
            pa = {p for c in grupos[a] for p in (c['a'], c['b'])}
            pb = {p for c in grupos[b] for p in (c['a'], c['b'])}
            SOL[a + '|' + b] = {'centros': round(float(ca @ cb), 3), 'pasajes_comunes': len(pa & pb)}
for x in INS:
    pisa = sorted(((k, v) for k, v in SOL.items() if x['instrumento'] in k.split('|')), key=lambda kv: -kv[1]['centros'])
    x['se_pisa_con'] = [{'con': [y for y in k.split('|') if y != x['instrumento']][0], **v} for k, v in pisa[:2]]
    fuerte = x['se_pisa_con'][0] if x['se_pisa_con'] else None
    if x['z'] >= 0.7 and x['sin_sustento'] < 0.5:
        x['veredicto'] = 'se sostiene'
    elif fuerte and fuerte['centros'] >= 0.6:
        x['veredicto'] = 'se pisa con otro'
    elif x['z'] >= 0.3:
        x['veredicto'] = 'débil'
    else:
        x['veredicto'] = 'no se distingue del azar'
INS.sort(key=lambda x: -x['z'])
print('\nbase al azar', round(base_mu, 3), round(base_sd, 3))
for x in INS:
    print(x['etiqueta'], '| z', x['z'], '| sin sustento', x['sin_sustento'], '|', x['veredicto'], '|', list(x['tipos'].items())[:3], '|', x['se_pisa_con'][:1])

# ── decisiones de la autora: qué tipo le da el material ──
DECS = []
for d in DEC:
    a, b = ubicar(d['origen']), ubicar(d['destino'])
    if a and b:
        for pid in (a, b):
            if pid not in PERF:
                PERF[pid] = perfil(pid)
        t, al, fz, pres, r, pct = clasificar(a, b)
    else:
        t, al, fz, pres = None, None, None, []
    DECS.append({'decision': d['decision'], 'tipo_autora': d.get('tipo_relacion'), 'tipo_material': t, 'senales': pres,
                 'fuerza': round(fz, 3) if fz is not None else None, 'de': d['origen']['sitio'], 'a': d['destino']['sitio'],
                 'emergente': (d.get('emergente') or '')[:160]})
print('\ndecisiones:')
for x in DECS:
    print(' ', x['decision'], '|', x['tipo_autora'], '→', x['tipo_material'], x['senales'], x['fuerza'], '|', x['de'], '→', x['a'])

# ── herramientas: procedimientos de escritura, por la forma de los pasajes ──
# Cada pasaje del cuerpo se describe por su forma (no por lo que dice) y se
# agrupan; cada grupo es un procedimiento que el cuerpo usa.
from criterios_base import EN as _EN
obra_de_clave = collections.defaultdict(set)
for p in PAS:
    for c in set(CLAVES[p['id']]):
        obra_de_clave[c].add(p.get('obra_clave') or p['sitio'])
SIMB = re.compile(r'[=+×÷<>≤≥∈∉∀∃∑∫√≠≈∞→←↔⇔⇒∧∨¬|/\\^_{}\[\]()0-9]')


def forma(p):
    t = p['texto']; ws = [w.lower() for w in PAL.findall(t)]; n = max(1, len(ws))
    lineas = [l for l in t.split('\n') if l.strip()]
    ks = CLAVES[p['id']]
    rep = sum(1 for i, w in enumerate(ws) if w in ws[max(0, i - 2):i]) / n
    sk = ' '.join(ws); reg = [0, 0]
    for canon, g in OPS:
        reg[g] += len(re.findall(r'\b' + r'\s+'.join(r'\w+' if x == 'X' else re.escape(x) for x in canon.split()) + r'\b', sk))
    return [sum(1 for l in lineas if len(l.split()) <= 8) / max(1, len(lineas)),        # verso
            len(re.findall(r'[^\w\s]', t)) / n,                                       # cortes (puntuación)
            rep,                                                                      # repetición
            len(SIMB.findall(t)) / max(1, len(t)) * 100,                              # notación
            sum(1 for c in ks if len(obra_de_clave[c]) == 1) / max(1, len(ks)),       # neologismo / término propio
            100 * reg[REG_ARG] / n, 100 * reg[1 - REG_ARG] / n,                      # operadores
            sum(1 for w in ws if w in _EN) / n,                                       # otra lengua
            sum(1 for w in ws if w in ('yo', 'me', 'mi', 'mí', 'conmigo')) / n]       # primera persona


FNOM = ['verso', 'cortes', 'repetición', 'notación', 'término propio', 'argumentativo', 'anafórico', 'otra lengua', 'primera persona']
cuerpo = [p for p in PAS if len(CLAVES[p['id']]) >= 25]
F = np.array([forma(p) for p in cuerpo])
# un procedimiento está «marcado» en un pasaje si está en el 5 % más alto del
# cuerpo (y no es cero)
UMB = {i: float(np.quantile(F[:, i], 0.95)) for i in range(len(FNOM))}
MARCA = np.array([[F[r, i] > 0 and F[r, i] >= UMB[i] for i in range(len(FNOM))] for r in range(len(F))])
DEF_F = {
    'verso': ('verso', 'Escritura en líneas cortas: el corte de línea como unidad.'),
    'cortes': ('corte', 'La puntuación fragmenta la frase: guiones, paréntesis, barras, dos puntos en cadena.'),
    'repetición': ('repetición', 'La misma palabra vuelve de inmediato (a una o dos palabras de distancia).'),
    'notación': ('notación', 'Símbolos, fórmulas, números o esquemas dentro del texto.'),
    'término propio': ('acuñación', 'Términos que solo aparecen en esa obra: palabras hechas para ella.'),
    'argumentativo': ('argumentación', 'Operadores argumentativos del cuerpo (si y sólo si, a su vez, por lo tanto, es decir).'),
    'anafórico': ('anáfora', 'Construcciones anafóricas del cuerpo (ni… ni…, me… me…, cual si… fuera).'),
    'otra lengua': ('otra lengua', 'Pasajes en otra lengua o con otra lengua metida en el castellano.'),
    'primera persona': ('primera persona', 'El yo en primer plano.'),
}
HERR = []
for i, k in enumerate(FNOM):
    idx = np.where(MARCA[:, i])[0]
    if not len(idx):
        continue
    obras_c = collections.Counter(cuerpo[r].get('obra_clave') or cuerpo[r]['sitio'] for r in idx)
    anios = [anio(o) for o in obras_c.elements() if anio(o)]
    # con qué otros procedimientos se combina más que el azar
    comb = []
    for j2, k2 in enumerate(FNOM):
        if j2 == i:
            continue
        p_ab = MARCA[idx, j2].mean(); p_b = MARCA[:, j2].mean()
        if p_b > 0 and p_ab / p_b >= 2 and MARCA[idx, j2].sum() >= 10:
            comb.append((DEF_F[k2][0], round(float(p_ab / p_b), 1)))
    comb.sort(key=lambda x: -x[1])
    top = idx[np.argsort(-F[idx, i])][:3]
    HERR.append({'herramienta': DEF_F[k][0], 'definicion': DEF_F[k][1], 'pasajes': int(len(idx)), 'obras': len(obras_c),
                 'concentracion': round(obras_c.most_common(1)[0][1] / len(idx), 2),
                 'obras_top': [o for o, _ in obras_c.most_common(6)],
                 'anios': [round(float(np.quantile(anios, q)), 1) for q in (0.1, 0.5, 0.9)] if anios else None,
                 'umbral': round(UMB[i], 4), 'se_combina_con': comb[:4],
                 'ejemplos': [{'obra': cuerpo[r].get('obra_clave') or cuerpo[r]['sitio'], 'texto': re.sub(r'\s+', ' ', cuerpo[r]['texto'])[:280]} for r in top]})
HERR.sort(key=lambda h: -h['obras'])
print()
for h in HERR:
    print(h['herramienta'], '| pasajes', h['pasajes'], '| obras', h['obras'], '| conc', h['concentracion'], '|', h['obras_top'][:3], h['anios'], '| combina', h['se_combina_con'])
SILF = None

json.dump({'senales': SENALES, 'base': {k: [round(float(np.quantile(v, q)), 3) for q in (0.5, 0.9)] for k, v in BASE.items()},
           'tipos': CATS, 'instrumentos': INS, 'solapes': SOL, 'base_azar': [round(base_mu, 3), round(base_sd, 3)],
           'decisiones': DECS, 'propuestas': len(CASOS), 'ubicadas': len(ubicados), 'asignacion': ASIG,
           'herramientas': HERR, 'formas': FNOM},
          open('categorias.json', 'w'), ensure_ascii=False, indent=1)
print('listo')
