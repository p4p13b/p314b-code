"""Fase 8 · Aire en la cuerda y De embriaguez y pathos: el mismo cuerpo de
cut-up pasado por dos aleatorizaciones (la autora lo confirmó), ubicado en
el tiempo contra todo lo que vino antes y después.

Nada de esto parte de listas de la autora: todo sale del material.

  posicion       dónde caen las dos obras en la cronología (fechas.json) y
                 qué hay antes y después
  pares          cada pasaje de una contra el más parecido de la otra
                 (TF-IDF de lemas, coseno): común (≥ 0.6), variante
                 (0.4–0.6) o propio (< 0.4)
  trayectorias   comunes: tramos que conservan el orden en las dos tiradas
                 (el azar no los separó); únicas: tramos seguidos de pasajes
                 propios de cada tirada, con su léxico distintivo
  conceptos      lemas que nacen en estas obras (ausentes antes, presentes
                 después en ≥ 2 obras) y lemas que se fundan acá (existían al
                 margen y desde acá se sostienen); en qué cuerpo nacen
  herramientas   los procedimientos de la fase 7 (y sus combinaciones) que
                 surgen o se intensifican acá y siguen después
  criterios      los criterios intrínsecos (criterios.json) que cambian acá y
                 cuánto de ese cambio persiste después
  diagonales     puentes: un pasaje anterior y uno posterior sin relación
                 directa que se tocan solo a través de un pasaje de estas obras
                 (ningún otro pasaje del cuerpo hace de puente); comparado con
                 el mismo cálculo sobre las obras contemporáneas
  instrumentos   los puentes agrupados por el término que los sostiene: cada
                 grupo es un instrumento que surge del flujo relacional

Escribe cutup.json (carpeta de trabajo); exportar.py lo pasa a
../datos/fase8-cutup.json.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
from fechas_base import anio_obra
import json, math, re, collections, random, statistics
import numpy as np
from lematica import tokens, norm, VACIAS, EXTRA
from clusters_base import GENERICAS
from criterios_base import EN as _EN

random.seed(8); np.random.seed(8)
from cutup_desc import DESCRIPCION
A, B = 'aire-en-la-cuerda', 'de-embriaguez-y-pathos'
AB = (A, B)
# «Lie, Lay, Ley» (I - Estudio, ~sept. 2020) comparte dos tercios de sus
# pasajes con el cuerpo del cut-up (se mide abajo): es la base anterior de
# ese cuerpo. No cuenta como «antes» ni como «después»: es la misma familia.
BASE = 'lie-lay-ley'
FAM = set(AB) | {BASE}
P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
PAS, META = P['pasajes'], P['meta']['sitios']
FECHAS = json.load(open('fechas.json'))
# Los cinco de Estudio que se subieron después de armar fechas.json: por su
# número en la carpeta (entre «El Hecho», 13, oct. 2019, y «Nigromancias»,
# 19, may. 2020). Confianza baja, como el resto de los fechados por orden.
for slug, f in (('cuerpo', '2019-11-15'), ('torcion', '2019-12-10'), ('3rd-comment', '2020-01-10'),
                ('autopoiesis', '2020-02-10'), ('bried-frain', '2020-03-10')):
    FECHAS.setdefault(slug, {'punto': f, 'carpeta': 'I - Estudio', 'fuente': 'orden', 'confianza': 'baja'})
EST = json.load(open('estructural.json'))
VOC = EST['voc']; VID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy').astype(np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
EM = json.load(open('emergencia.json'))
CRIT = json.load(open('criterios.json'))
TIT = {o: m.get('titulo', o) for o, m in META.items()}


def anio(o):
    return anio_obra(FECHAS, o)


T0 = anio(A)
sitio = lambda p: p['sitio']
PERIODO = {}
for o in META:
    t = anio(o)
    PERIODO[o] = 'ab' if o in AB else 'base' if o == BASE else None if t is None else 'antes' if t < T0 - 0.005 else 'despues' if t > T0 + 0.005 else 'mismo'
recortar = lambda t, n=260: (lambda s: s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…')(re.sub(r'\s+', ' ', t).strip())

# ── claves (lemas con las reglas de la página + lemas.json) ──
CLAVES = {}
df = collections.Counter()
FORMAS = collections.defaultdict(collections.Counter)
for p in PAS:
    tk = tokens(p['texto'])
    ks = [c if c == 'sí' else norm(c) for _, c in tk]
    for (f, _), k in zip(tk, ks):
        FORMAS[k][f] += 1
    CLAVES[p['id']] = ks
    df.update(set(ks))
ver = lambda c: FORMAS[c].most_common(1)[0][0] if FORMAS.get(c) else c  # la forma más usada, para mostrar
N = len(PAS)
idf = {c: math.log(N / n) for c, n in df.items()}
CUENTA = {c for c in df if c not in VACIAS and c not in EXTRA and c not in GENERICAS and len(c) >= 4}
por_sitio = collections.defaultdict(list)
for p in PAS:
    por_sitio[sitio(p)].append(p)
for o in por_sitio:
    por_sitio[o].sort(key=lambda p: (p.get('pdf_pagina') or 0, p['id']))


def tfidf(pid):
    tf = collections.Counter(c for c in CLAVES[pid] if c in CUENTA)
    w = {c: (1 + math.log(n)) * idf[c] for c, n in tf.items()}
    nl = math.sqrt(sum(x * x for x in w.values())) or 1
    return {c: x / nl for c, x in w.items()}


# ── 1. posición en el tiempo ──
orden = sorted((o for o in META if anio(o) is not None), key=anio)
posicion = {
    'fecha': FECHAS[A].get('punto'), 'fuente': FECHAS[A].get('fuente'), 'confianza': FECHAS[A].get('confianza'),
    'nota': 'La autora corrigió la fecha a ~2022 (la base común es anterior; cada copia se revisó por separado).',
    'antes': [{'obra': TIT.get(o, o), 'slug': o, 'fecha': FECHAS[o]['punto']} for o in orden if PERIODO[o] == 'antes'],
    'despues': [{'obra': TIT.get(o, o), 'slug': o, 'fecha': FECHAS[o]['punto']} for o in orden if PERIODO[o] in ('despues', 'mismo')],
    'sin_fecha': sorted(TIT.get(o, o) for o in META if anio(o) is None),
    'base': {'obra': TIT.get(BASE, BASE), 'slug': BASE, 'fecha': FECHAS.get(BASE, {}).get('punto'),
             'fuente': FECHAS.get(BASE, {}).get('fuente'), 'confianza': FECHAS.get(BASE, {}).get('confianza')},
}

# ── 2. pares A ↔ B ──
LA, LB = por_sitio[A], por_sitio[B]
VA = [tfidf(p['id']) for p in LA]
VB = [tfidf(p['id']) for p in LB]
post = collections.defaultdict(list)
for j, v in enumerate(VB):
    for c, x in v.items():
        post[c].append((j, x))
S = np.zeros((len(LA), len(LB)), dtype=np.float32)
for i, v in enumerate(VA):
    for c, x in v.items():
        for j, y in post.get(c, ()):
            S[i, j] += x * y


def clase(s):
    return 'común' if s >= 0.6 else 'variante' if s >= 0.4 else 'propio'


mejorA = S.argmax(1); scoreA = S.max(1)
mejorB = S.argmax(0); scoreB = S.max(0)
claseA = [clase(s) for s in scoreA]
claseB = [clase(s) for s in scoreB]
CLASE = {}
for i, p in enumerate(LA):
    CLASE[p['id']] = claseA[i]
for j, p in enumerate(LB):
    CLASE[p['id']] = claseB[j]
mutuos = [(i, int(mejorA[i])) for i in range(len(LA)) if mejorB[mejorA[i]] == i and scoreA[i] >= 0.6]


def pag(p):
    return p.get('pdf_pagina')


def calibrar(pa, pb):
    ia = next((i for i, p in enumerate(LA) if pag(p) == pa), None)
    jb = next((j for j, p in enumerate(LB) if pag(p) == pb), None)
    return None if ia is None or jb is None else {'aire': pa, 'embriaguez': pb, 'coseno': round(float(S[ia, jb]), 3),
                                                  'es_el_mejor': int(mejorA[ia]) == jb}


cuenta_cl = lambda cl: dict(collections.Counter(cl))
# gemelos léxicos (≥ 0.5) de cualquier pasaje del cuerpo en Aire o Embriaguez
postAB = collections.defaultdict(list)
for k, v in enumerate(VA + VB):
    for c, x in v.items():
        postAB[c].append((k, x))


def gemelo_ab(pid):
    sc = collections.Counter()
    for c, x in tfidf(pid).items():
        for k, y in postAB.get(c, ()):
            sc[k] += x * y
    if not sc:
        return None, 0.0
    k, v = sc.most_common(1)[0]
    return ('aire' if k < len(LA) else 'embriaguez'), v


GEMELO = {}
for p in PAS:
    if p['sitio'] not in AB and len(CLAVES[p['id']]) >= 25:
        GEMELO[p['id']] = gemelo_ab(p['id'])
otras_fam = []
for o, lst in por_sitio.items():
    if o in AB:
        continue
    g = [GEMELO[p['id']] for p in lst if p['id'] in GEMELO]
    n = sum(1 for x in g if x[1] >= 0.5)
    if g and n / len(g) >= 0.05:
        otras_fam.append({'obra': TIT.get(o, o), 'slug': o, 'fecha': FECHAS.get(o, {}).get('punto'), 'pasajes': len(g), 'compartidos': n,
                          'con_aire': sum(1 for x in g if x[1] >= 0.5 and x[0] == 'aire'),
                          'con_embriaguez': sum(1 for x in g if x[1] >= 0.5 and x[0] == 'embriaguez')})
# orden: cuánto reordenó el azar (correlación de rangos entre las posiciones
# de los pares mutuos en una y otra tirada)
if len(mutuos) > 2:
    ra = np.argsort(np.argsort([i for i, _ in mutuos])); rb = np.argsort(np.argsort([j for _, j in mutuos]))
    spearman = float(np.corrcoef(ra, rb)[0, 1])
else:
    spearman = None


def tercio_final(cl):
    n = len(cl); f = cl[int(n * 0.9):]
    return round(sum(1 for c in f if c == 'propio') / max(1, len(f)), 2)


pares = {'pasajes': {'aire': len(LA), 'embriaguez': len(LB)}, 'aire': cuenta_cl(claseA), 'embriaguez': cuenta_cl(claseB),
         'mutuos': len(mutuos), 'orden_spearman': round(spearman, 3) if spearman is not None else None,
         'propio_en_el_ultimo_decimo': {'aire': tercio_final(claseA), 'embriaguez': tercio_final(claseB)},
         'calibracion': [x for x in (calibrar(407, 265), calibrar(185, 150)) if x], 'mismo_cuerpo_en_otras': otras_fam}

# ── 2b. gemelas: para la acción «gemela» de los dos posteos-PDF ──
# Por cada página, su gemela en la otra tirada (la de mayor coseno), la clase
# del par y lo que cambia: los términos que solo están de un lado (por peso).
def _cambia(va, vb, k=8):
    sa = sorted((c for c in va if c not in vb), key=lambda c: -va[c])[:k]
    sb = sorted((c for c in vb if c not in va), key=lambda c: -vb[c])[:k]
    return [ver(c) for c in sa], [ver(c) for c in sb]


def _gemelas(L, Vs, otraL, otraVs, mejor, score, cl):
    out = {}
    for i, p in enumerate(L):
        j = int(mejor[i]); q = otraL[j]
        if pag(p) is None or pag(q) is None:
            continue
        solo, otra = _cambia(Vs[i], otraVs[j])
        out[str(pag(p))] = {'p': pag(q), 's': round(float(score[i]), 2), 'c': cl[i], 'solo': solo, 'otra': otra}
    return out


GEMELAS = {
    A: {'otra': B, 'titulo_otra': TIT.get(B, B), 'paginas': _gemelas(LA, VA, LB, VB, mejorA, scoreA, claseA)},
    B: {'otra': A, 'titulo_otra': TIT.get(A, A), 'paginas': _gemelas(LB, VB, LA, VA, mejorB, scoreB, claseB)},
}
with open(RAIZ + 'sitio/gemelas.json', 'w', encoding='utf-8') as f:
    json.dump({'descripcion': 'Gemelas entre Aire en la cuerda y De embriaguez y pathos (el mismo cuerpo de cut-up, dos tiradas). '
                              'Lo arma a mano sitio/matriz/anexo/scripts/cutup.py; lo lee la acción «gemela» de los posteos-PDF.',
               'umbrales': {'común': 0.6, 'variante': 0.4}, 'obras': GEMELAS}, f, ensure_ascii=False, separators=(',', ':'))
    f.write('\n')

# ── 3. trayectorias ──
# comunes: pares mutuos consecutivos en las dos (el siguiente de uno es el
# siguiente, o el de dos más allá, del otro)
mutuos.sort()
tramos = []
cur = [mutuos[0]] if mutuos else []
for (i, j) in mutuos[1:]:
    pi, pj = cur[-1]
    if 0 < i - pi <= 2 and 0 < j - pj <= 2:
        cur.append((i, j))
    else:
        if len(cur) >= 2:
            tramos.append(cur)
        cur = [(i, j)]
if len(cur) >= 2:
    tramos.append(cur)


def lexico_de(ids, contra_ids, k=8):
    a = collections.Counter(c for pid in ids for c in CLAVES[pid] if c in CUENTA)
    b = collections.Counter(c for pid in contra_ids for c in CLAVES[pid] if c in CUENTA)
    na, nb = sum(a.values()) or 1, sum(b.values()) or 1
    sc = {c: math.log((a[c] + .5) / na) - math.log((b[c] + .5) / nb) for c in a if a[c] >= 2}
    return [c for c, _ in sorted(sc.items(), key=lambda x: -x[1])[:k]]


todos_ab = [p['id'] for p in LA + LB]
tray_comunes = []
for t in sorted(tramos, key=len, reverse=True)[:12]:
    ids = [LA[i]['id'] for i, _ in t]
    tray_comunes.append({'largo': len(t), 'aire': [pag(LA[t[0][0]]), pag(LA[t[-1][0]])],
                         'embriaguez': [pag(LB[t[0][1]]), pag(LB[t[-1][1]])],
                         'lexico': [ver(c) for c in lexico_de(ids, todos_ab)], 'texto': recortar(LA[t[0][0]]['texto'])})


def tramos_propios(L, cl, nombre):
    out, cur = [], []
    for k, c in enumerate(cl + ['fin']):
        if c == 'propio':
            cur.append(k)
        else:
            if len(cur) >= 3:
                out.append(cur)
            cur = []
    res = []
    otra = LB if nombre == 'aire' else LA
    for t in sorted(out, key=len, reverse=True)[:8]:
        ids = [L[k]['id'] for k in t]
        res.append({'obra': nombre, 'largo': len(t), 'paginas': [pag(L[t[0]]), pag(L[t[-1]])],
                    'lexico': [ver(c) for c in lexico_de(ids, [p['id'] for p in otra])], 'texto': recortar(L[t[0]]['texto'])})
    return res


tray_unicas = tramos_propios(LA, claseA, 'aire') + tramos_propios(LB, claseB, 'embriaguez')

# ── 4. conceptos: nacen o se fundan acá ──
cnt = {o: collections.Counter(c for p in por_sitio[o] for c in CLAVES[p['id']] if c in CUENTA) for o in por_sitio}
tok = {o: sum(cnt[o].values()) or 1 for o in cnt}
antes_o = [o for o in cnt if PERIODO.get(o) == 'antes']
desp_o = [o for o in cnt if PERIODO.get(o) in ('despues', 'mismo')]
C_antes = sum((cnt[o] for o in antes_o), collections.Counter()); T_antes = sum(tok[o] for o in antes_o)
C_ab = cnt[A] + cnt[B]; T_ab = tok[A] + tok[B]
C_desp = sum((cnt[o] for o in desp_o), collections.Counter()); T_desp = sum(tok[o] for o in desp_o)
en_desp = collections.defaultdict(list)
for o in desp_o:
    for c in cnt[o]:
        en_desp[c].append(o)
cuerpo_de = collections.defaultdict(collections.Counter)  # en qué parte del cut-up cae
for p in LA + LB:
    for c in CLAVES[p['id']]:
        if c in CUENTA:
            cuerpo_de[c][('aire ' if p['sitio'] == A else 'embriaguez ') + CLASE[p['id']]] += 1


def donde(c):
    d = cuerpo_de[c]; com = d['aire común'] + d['embriaguez común'] + d['aire variante'] + d['embriaguez variante']
    pa, pb = d['aire propio'], d['embriaguez propio']
    tot = com + pa + pb or 1
    if com / tot >= 0.5:
        return 'cuerpo común'
    return 'propio de Aire' if pa > pb * 2 else 'propio de Embriaguez' if pb > pa * 2 else 'repartido'


def ejemplo(c, obras):
    for o in obras:
        for p in por_sitio[o]:
            if c in CLAVES[p['id']]:
                return {'obra': TIT.get(o, o), 'texto': recortar(p['texto'], 200)}
    return None


nacen = []
for c, n in C_ab.items():
    if C_antes[c] or n < 3 or len(en_desp[c]) < 2 or not (cnt[A][c] or cnt[B][c]) or c in _EN:
        continue
    peso = len(en_desp[c]) * math.log1p(C_desp[c]) * math.log1p(n)
    nacen.append({'concepto': ver(c), 'clave': c, 'ya_en_la_base': cnt[BASE][c] > 0, 'en_ab': n, 'aire': cnt[A][c], 'embriaguez': cnt[B][c], 'obras_despues': len(en_desp[c]),
                  'usos_despues': C_desp[c], 'peso': round(peso, 2), 'cuerpo': donde(c),
                  'despues_en': [TIT.get(o, o) for o in sorted(en_desp[c], key=anio)][:6],
                  'ejemplo': ejemplo(c, AB)})
nacen.sort(key=lambda x: -x['peso'])
ESTANDAR = {c for c in CUENTA if sum(1 for o in cnt if cnt[o][c]) >= len(cnt) / 2}
fundan = []
for c, n in C_ab.items():
    if not C_antes[c] or n < 8 or c in _EN:
        continue
    r_antes = C_antes[c] / T_antes; r_ab = n / T_ab; r_desp = C_desp[c] / T_desp if T_desp else 0
    obras_antes = sum(1 for o in antes_o if cnt[o][c])
    if r_ab < 6 * r_antes or r_desp < 3 * r_antes or obras_antes > 4 or len(en_desp[c]) < 4 or c in ESTANDAR:
        continue
    fundan.append({'concepto': ver(c), 'clave': c, 'ya_en_la_base': cnt[BASE][c] > 0, 'antes': C_antes[c], 'obras_antes': obras_antes, 'en_ab': n, 'obras_despues': len(en_desp[c]),
                   'salto': round(r_ab / r_antes, 1), 'sostiene': round(r_desp / r_antes, 1),
                   'peso': round(math.log(r_ab / r_antes) * len(en_desp[c]) * math.log1p(n), 2), 'cuerpo': donde(c),
                   'despues_en': [TIT.get(o, o) for o in sorted(en_desp[c], key=anio)][:6], 'ejemplo': ejemplo(c, AB)})
fundan.sort(key=lambda x: -x['peso'])
# conceptos de la fase 6 (operados como conceptos por el cuerpo): primera
# obra donde aparece su familia y salto en estas obras
fase6 = []
for f in EM['conceptos']:
    fam = set(f['familia']) | {f['clave']}
    pres = {o: sum(cnt[o][c] for c in fam) for o in cnt}
    con = sorted((o for o, v in pres.items() if v and anio(o) is not None), key=anio)
    if not con:
        continue
    r = lambda os_: sum(pres[o] for o in os_) / max(1, sum(tok[o] for o in os_))
    ra, rab, rd = r(antes_o), r(list(AB)), r(desp_o)
    fase6.append({'concepto': ver(f['clave']), 'primera': TIT.get(con[0], con[0]), 'nace_aca': con[0] in AB,
                  'antes': round(ra * 1e4, 2), 'ab': round(rab * 1e4, 2), 'despues': round(rd * 1e4, 2),
                  'salto': round(rab / ra, 1) if ra else None})
fase6_aca = sorted([x for x in fase6 if x['nace_aca'] or (x['salto'] or 0) >= 3], key=lambda x: -(x['salto'] or 99))

# ── 5. herramientas (procedimientos de la fase 7, por pasaje) ──
OPS = [(o['canon'], o['registro']) for o in EM['operadores']]
REG_ARG = next((o['registro'] for o in EM['operadores'] if re.search('sólo si|por lo tanto|es decir', o['canon'])), 1)
PAL = re.compile(r"[^\W\d_]+", re.U)
SIMB = re.compile(r'[=+×÷<>≤≥∈∉∀∃∑∫√≠≈∞→←↔⇔⇒∧∨¬|/\\^_{}\[\]()0-9]')
obra_de_clave = collections.defaultdict(set)
for p in PAS:
    for c in set(CLAVES[p['id']]):
        obra_de_clave[c].add('cut-up' if p['sitio'] in FAM else p['sitio'])  # la familia cuenta como una obra


def forma(p):
    t = p['texto']; ws = [w.lower() for w in PAL.findall(t)]; n = max(1, len(ws))
    lineas = [l for l in t.split('\n') if l.strip()]
    ks = CLAVES[p['id']]
    rep = sum(1 for i, w in enumerate(ws) if w in ws[max(0, i - 2):i]) / n
    sk = ' '.join(ws); reg = [0, 0]
    for canon, g in OPS:
        reg[g] += len(re.findall(r'\b' + r'\s+'.join(r'\w+' if x == 'X' else re.escape(x) for x in canon.split()) + r'\b', sk))
    return [sum(1 for l in lineas if len(l.split()) <= 8) / max(1, len(lineas)), len(re.findall(r'[^\w\s]', t)) / n, rep,
            len(SIMB.findall(t)) / max(1, len(t)) * 100, sum(1 for c in ks if len(obra_de_clave[c]) == 1) / max(1, len(ks)),
            100 * reg[REG_ARG] / n, 100 * reg[1 - REG_ARG] / n, sum(1 for w in ws if w in _EN) / n,
            sum(1 for w in ws if w in ('yo', 'me', 'mi', 'mí', 'conmigo')) / n]


FNOM = ['verso', 'corte', 'repetición', 'notación', 'acuñación', 'argumentación', 'anáfora', 'otra lengua', 'primera persona']
cuerpo = [p for p in PAS if len(CLAVES[p['id']]) >= 25]
F = np.array([forma(p) for p in cuerpo])
UMB = [float(np.quantile(F[:, i], 0.95)) for i in range(len(FNOM))]
MARCA = (F > 0) & (F >= np.array(UMB))
per = np.array([PERIODO.get(p['sitio']) for p in cuerpo], dtype=object)
m_antes = per == 'antes'; m_ab = per == 'ab'; m_desp = (per == 'despues') | (per == 'mismo')
m_A = np.array([p['sitio'] == A for p in cuerpo]); m_B = np.array([p['sitio'] == B for p in cuerpo])
tasa = lambda col, m: float(col[m].mean()) if m.sum() else 0.0


def veredicto(ra, rab, rd):
    if rab >= 1.5 * max(ra, 1e-4) and rd >= 1.3 * max(ra, 1e-4):
        return 'surge acá y se desarrolla'
    if rab >= 1.5 * max(ra, 1e-4):
        return 'se concentra acá, no sigue'
    if rd >= 1.5 * max(rab, 1e-4) and rab >= 1.2 * max(ra, 1e-4):
        return 'empieza acá, crece después'
    return 'viene de antes'


herramientas = []
for i, nom in enumerate(FNOM):
    if nom == 'verso':
        continue  # los pasajes vienen sin cortes de línea: no se puede medir
    col = MARCA[:, i]
    ra, rab, rd = tasa(col, m_antes), tasa(col, m_ab), tasa(col, m_desp)
    herramientas.append({'herramienta': nom, 'antes': round(ra * 100, 1), 'ab': round(rab * 100, 1), 'despues': round(rd * 100, 1),
                         'aire': round(tasa(col, m_A) * 100, 1), 'embriaguez': round(tasa(col, m_B) * 100, 1),
                         'veredicto': veredicto(ra, rab, rd)})
combos = []
for i in range(1, len(FNOM)):
    for j in range(i + 1, len(FNOM)):
        col = MARCA[:, i] & MARCA[:, j]
        ra, rab, rd = tasa(col, m_antes), tasa(col, m_ab), tasa(col, m_desp)
        n_ab = int(col[m_ab].sum())
        if n_ab < 4:
            continue
        v = veredicto(ra, rab, rd)
        if v == 'viene de antes':
            continue
        idx = [r for r in np.where(col & m_ab)[0]]
        r0 = max(idx, key=lambda r: F[r, i] / (UMB[i] or 1) + F[r, j] / (UMB[j] or 1))
        obras_d = collections.Counter(cuerpo[r]['sitio'] for r in np.where(col & m_desp)[0])
        combos.append({'herramienta': FNOM[i] + ' + ' + FNOM[j], 'antes': round(ra * 100, 2), 'ab': round(rab * 100, 2),
                       'despues': round(rd * 100, 2), 'pasajes_ab': n_ab, 'veredicto': v,
                       'sigue_en': [TIT.get(o, o) for o, _ in obras_d.most_common(5)],
                       'ejemplo': {'obra': TIT.get(cuerpo[r0]['sitio']), 'pagina': pag(cuerpo[r0]), 'texto': recortar(cuerpo[r0]['texto'], 220)}})
combos.sort(key=lambda x: -(x['ab'] / max(x['antes'], 0.05)))

# ── 6. criterios intrínsecos ──
MET = [('TTR', 'variedad léxica'), ('TTRinst', 'variedad de instancias'), ('Eg', 'grafemas (signos, huecos)'),
       ('Ef', 'finales (rima)'), ('Esint', 'saturación sintáctica'), ('DRI', 'repetición inmediata'),
       ('IIN', 'inconsistencia necesaria'), ('cq', 'curvatura del quantum'), ('costo', 'costo de integración')]
# (la hiperespecificidad no entra: Aire y Embriaguez comparten léxico, así que
# cada una parece menos específica de lo que es; es un artefacto del par)
criterios = []
for k, nombre in MET:
    va = [CRIT[o][k] for o in antes_o if o in CRIT and CRIT[o].get(k) is not None and CRIT[o].get('idioma', 'es') == 'es']
    vd = [CRIT[o][k] for o in desp_o if o in CRIT and CRIT[o].get(k) is not None and CRIT[o].get('idioma', 'es') == 'es']
    vab = [CRIT[o][k] for o in AB if o in CRIT and CRIT[o].get(k) is not None]
    if len(va) < 3 or not vab or not vd:
        continue
    ma, sa = statistics.mean(va), statistics.pstdev(va) or 1e-9
    mab, md = statistics.mean(vab), statistics.mean(vd)
    z = (mab - ma) / sa
    persiste = (md - ma) / (mab - ma) if abs(mab - ma) > 1e-12 else 0
    criterios.append({'criterio': k, 'nombre': nombre, 'antes': round(ma, 4), 'aire': round(CRIT[A][k], 4), 'embriaguez': round(CRIT[B][k], 4),
                      'despues': round(md, 4), 'z': round(z, 2), 'persiste': round(persiste, 2),
                      'veredicto': ('surge acá y persiste' if abs(z) >= 1 and persiste >= 0.5 else
                                    'surge acá, se diluye' if abs(z) >= 1 else 'sin cambio propio')})
criterios.sort(key=lambda x: -abs(x['z']))

# ── 7. diagonales: puentes que solo pasan por estas obras ──
CENTRO = None


def vec(pid):
    tf = collections.Counter(c for c in CLAVES[pid] if c in VID and c in CUENTA)
    if not tf:
        return None
    w = {c: (1 + math.log(n)) * idf[c] for c, n in tf.items()}
    v = sum(E[VID[c]] * x for c, x in w.items())
    return v / (np.linalg.norm(v) + 1e-9)


IDS, V = [], []
for p in PAS:
    if len(CLAVES[p['id']]) < 25:
        continue
    v = vec(p['id'])
    if v is not None:
        IDS.append(p['id']); V.append(v)
V = np.array(V, dtype=np.float32)
CENTRO = V.mean(0)
_, _, Vt = np.linalg.svd(V[np.random.choice(len(V), min(3000, len(V)), replace=False)] - CENTRO, full_matrices=False)
for k in range(3):
    V = V - np.outer((V - CENTRO) @ Vt[k], Vt[k])
V = V - CENTRO
V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
PID = {pid: i for i, pid in enumerate(IDS)}
SIT = np.array([None] * len(IDS), dtype=object)
_ps = {p['id']: p for p in PAS}
for pid, i in PID.items():
    SIT[i] = _ps[pid]['sitio']
PER = np.array([PERIODO.get(s) for s in SIT], dtype=object)
r = np.random.choice(len(V), (4000, 2))
azar = np.einsum('ij,ij->i', V[r[:, 0]], V[r[:, 1]])
HI = float(np.quantile(azar, 0.985)); MED = float(np.quantile(azar, 0.5))
limpio = np.array([GEMELO.get(pid, (None, 0))[1] < 0.5 for pid in IDS])  # no es el mismo texto que Aire/Embriaguez
i_antes = np.where((PER == 'antes') & limpio)[0]; i_desp = np.where(((PER == 'despues') | (PER == 'mismo')) & limpio)[0]
L_ = {pid: tfidf(pid) for pid in IDS}


def puentes(mediadores, excluir_sitios, topk=12):
    """Pares (antes, después) sin relación directa que se tocan solo a través
    de un mediador del conjunto (ningún pasaje de otro sitio hace de puente)."""
    fuera = np.array([s not in excluir_sitios for s in SIT])
    out = {}
    for m in mediadores:
        sb = V[i_antes] @ V[m]; sa = V[i_desp] @ V[m]
        cb = i_antes[np.argsort(-sb)[:topk]]; cb = cb[V[cb] @ V[m] >= HI]
        ca = i_desp[np.argsort(-sa)[:topk]]; ca = ca[V[ca] @ V[m] >= HI]
        for p in cb:
            for q in ca:
                if SIT[p] == SIT[q] or float(V[p] @ V[q]) >= MED:
                    continue
                fuerza = min(float(V[p] @ V[m]), float(V[q] @ V[m]))
                key = (p, q)
                if key not in out or out[key][1] < fuerza:
                    out[key] = (m, fuerza)
    # exclusividad: ningún pasaje fuera del conjunto (y de los dos extremos) hace de puente
    res = []
    for (p, q), (m, fz) in out.items():
        alt = np.minimum(V @ V[p], V @ V[q])
        alt[~fuera] = -1; alt[SIT == SIT[p]] = -1; alt[SIT == SIT[q]] = -1
        if alt.max() < HI:
            res.append((p, q, m, fz))
    return res


med_ab = [PID[p['id']] for p in LA + LB if p['id'] in PID]
pts = puentes(med_ab, FAM)
# contraste: el mismo cálculo con cada obra contemporánea (±1 año) como
# mediadora; puentes por pasaje mediador
contemp = [o for o in META if o not in FAM and anio(o) is not None and abs(anio(o) - T0) <= 1.0]
por_obra = []
for o in contemp:
    med = [i for i in range(len(IDS)) if SIT[i] == o]
    if len(med) < 20:
        continue
    random.shuffle(med)
    med = med[:300]
    por_obra.append({'obra': TIT.get(o, o), 'mediadores': len(med), 'puentes': len(puentes(med, {o})),
                     'por_pasaje': 0})
    por_obra[-1]['por_pasaje'] = round(por_obra[-1]['puentes'] / len(med), 2)


PRES = {c: sum(1 for o in cnt if cnt[o][c]) / len(cnt) for c in CUENTA}
T_tot = sum(tok.values())
C_tot = sum(cnt.values(), collections.Counter())
LIFT = {c: (C_ab[c] / T_ab) / (C_tot[c] / T_tot) for c in C_ab if C_tot[c]}


def comunes(p, m, q, k=4):
    # el término que sostiene el puente: presente en los tres (o en el
    # mediador y un extremo), pesado por cuánto es de Aire/Embriaguez y
    # descartando los que están en más de la mitad de las obras
    a, b, c = L_[IDS[p]], L_[IDS[m]], L_[IDS[q]]
    sh = {t: a[t] * b[t] * c[t] for t in set(a) & set(b) & set(c)}
    if len(sh) < 1:
        sh = {t: (a.get(t, 0) + c.get(t, 0)) * b[t] * 0.5 for t in b if t in a or t in c}
    sh = {t: x * math.log1p(LIFT.get(t, 1)) for t, x in sh.items() if PRES.get(t, 1) < 0.5}
    return [t for t, _ in sorted(sh.items(), key=lambda x: -x[1])[:k]]


def depende(m):
    pid = IDS[m]
    cl = CLASE.get(pid)
    if cl in ('común', 'variante'):
        return 'ambas (cuerpo común)'
    return 'solo Aire' if SIT[m] == A else 'solo Embriaguez'


diag = collections.defaultdict(list)
for p, q, m, fz in pts:
    diag[(SIT[p], SIT[q])].append((p, q, m, fz))
diagonales = []
for (sp, sq), lst in sorted(diag.items(), key=lambda kv: -(len(kv[1]) * max(x[3] for x in kv[1]))):
    p, q, m, fz = max(lst, key=lambda x: x[3])
    dep = collections.Counter(depende(x[2]) for x in lst)
    diagonales.append({'desde': TIT.get(sp, sp), 'desde_anio': FECHAS.get(sp, {}).get('punto'),
                       'hacia': TIT.get(sq, sq), 'hacia_anio': FECHAS.get(sq, {}).get('punto'),
                       'puentes': len(lst), 'fuerza': round(fz, 3), 'depende_de': dict(dep), 'por': [ver(c) for c in comunes(p, m, q)],
                       'ejemplo': {'desde': recortar(_ps[IDS[p]]['texto'], 220),
                                   'pasa_por': {'obra': TIT.get(SIT[m]), 'pagina': pag(_ps[IDS[m]]), 'texto': recortar(_ps[IDS[m]]['texto'], 220)},
                                   'hacia': recortar(_ps[IDS[q]]['texto'], 220)}})

# ── 8. instrumentos: los puentes agrupados por el término que los sostiene ──
grupos = collections.defaultdict(list)
for p, q, m, fz in pts:
    cs = comunes(p, m, q, 2)
    if cs:
        grupos[cs[0]].append((p, q, m, fz, cs))
instrumentos = []
for t, lst in grupos.items():
    pares_o = {(SIT[p], SIT[q]) for p, q, *_ in lst}
    obras = {SIT[p] for p, *_ in lst} | {SIT[q] for _, q, *_ in lst}
    if len(lst) < 3 or len(pares_o) < 2:
        continue
    seg = collections.Counter(c for *_, cs in lst for c in cs[1:])
    dep = collections.Counter(depende(m) for _, _, m, _, _ in lst)
    antes_ = collections.Counter(SIT[p] for p, *_ in lst); desp_ = collections.Counter(SIT[q] for _, q, *_ in lst)
    p, q, m, fz, _ = max(lst, key=lambda x: x[3])
    instrumentos.append({'instrumento': ver(t) + (' / ' + ver(seg.most_common(1)[0][0]) if seg else ''), 'termino': ver(t),
                         'puentes': len(lst), 'pares_de_obras': len(pares_o), 'obras': len(obras),
                         'peso': round(len(lst) * math.log1p(len(pares_o)) * statistics.mean(x[3] for x in lst), 2),
                         'depende_de': dict(dep),
                         'definicion': 'Lleva de %s a %s a través de «%s» en %s.' % (
                             ', '.join(TIT.get(o, o) for o, _ in antes_.most_common(2)),
                             ', '.join(TIT.get(o, o) for o, _ in desp_.most_common(2)), ver(t), dep.most_common(1)[0][0]),
                         'evidencia': {'desde': {'obra': TIT.get(SIT[p]), 'texto': recortar(_ps[IDS[p]]['texto'], 200)},
                                       'pasa_por': {'obra': TIT.get(SIT[m]), 'pagina': pag(_ps[IDS[m]]), 'texto': recortar(_ps[IDS[m]]['texto'], 200)},
                                       'hacia': {'obra': TIT.get(SIT[q]), 'texto': recortar(_ps[IDS[q]]['texto'], 200)}}})
instrumentos.sort(key=lambda x: -x['peso'])

pp_ab = round(len(pts) / max(1, len(med_ab)), 2)
por_obra.sort(key=lambda x: -x['por_pasaje'])
contraste = {'umbral_puente': round(HI, 3), 'umbral_sin_relacion': round(MED, 3),
             'mediadores_ab': len(med_ab), 'puentes_ab': len(pts), 'por_pasaje_ab': pp_ab,
             'contemporaneas': por_obra,
             'mediana_contemporaneas': round(statistics.median([x['por_pasaje'] for x in por_obra]), 2) if por_obra else None}

json.dump({'posicion': posicion, 'pares': pares, 'trayectorias_comunes': tray_comunes, 'trayectorias_unicas': tray_unicas,
           'conceptos_nacen': nacen[:30], 'conceptos_fundan': fundan[:25], 'conceptos_fase6': fase6_aca,
           'herramientas': herramientas, 'herramientas_combinadas': combos[:12], 'criterios': criterios,
           'diagonales': diagonales[:25], 'diagonales_total': len(diagonales), 'instrumentos': instrumentos[:15],
           'contraste': contraste}, open('cutup.json', 'w'), ensure_ascii=False, indent=1)
# y directo a ../datos/ (exportar.py hace lo mismo si se corre todo)
import os
from _rutas import DATOS
with open(os.path.join(DATOS, 'fase8-cutup.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(json.load(open('cutup.json')), descripcion=DESCRIPCION), f, ensure_ascii=False, indent=1)
    f.write('\n')

print('posición', posicion['fecha'], '| antes', len(posicion['antes']), '| después', len(posicion['despues']))
print('pares', pares)
print('trayectorias comunes', len(tramos), [t['largo'] for t in tray_comunes[:6]], '| únicas', [(t['obra'], t['largo']) for t in tray_unicas[:6]])
print('nacen', [(x['concepto'], x['obras_despues'], x['cuerpo'], x['ya_en_la_base']) for x in nacen[:18]])
print('fundan', [(x['concepto'], x['salto'], x['sostiene'], x['ya_en_la_base']) for x in fundan[:14]])
print('fase6', [(x['concepto'], x['primera'], x['salto']) for x in fase6_aca[:10]])
print('herramientas', [(h['herramienta'], h['antes'], h['ab'], h['despues'], h['veredicto']) for h in herramientas])
print('combinadas', [(c['herramienta'], c['antes'], c['ab'], c['despues'], c['veredicto']) for c in combos[:8]])
print('criterios', [(c['criterio'], c['z'], c['persiste'], c['veredicto']) for c in criterios])
print('contraste', {k: v for k, v in contraste.items() if k != 'contemporaneas'}, [(x['obra'], x['por_pasaje']) for x in por_obra])
print('mismo cuerpo en', otras_fam)
print('diagonales', len(diagonales), [(d['desde'], d['hacia'], d['puentes'], d['depende_de'], d['por']) for d in diagonales[:8]])
print('instrumentos', [(i['instrumento'], i['puentes'], i['pares_de_obras'], i['depende_de']) for i in instrumentos[:10]])
