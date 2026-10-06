"""Experimento «tercero»: para cada par de páginas gemelas de Aire en la
cuerda y De embriaguez y pathos, el fragmento de un tercer texto con el que
se relacionan.

Cada par se parte en tres:
  común       los términos que las dos páginas comparten (peso: el menor
              de los dos)
  propio A    los que solo están en la página de Aire
  propio E    los que solo están en la de Embriaguez
y se busca el tercero de cuatro maneras, de lo estrecho a lo amplio:
  común       solo lo compartido: coincidencia estructural
  común + E   lo compartido más lo propio de Embriaguez
  común + A   lo compartido más lo propio de Aire
  todo        las dos páginas enteras
Puntaje: coseno en el espacio estructural (fase 2, sin las tres
componentes comunes del cuerpo, como en las fases 6 a 8) corregido por
«hubs» (CSLS: a cada pasaje se le descuenta cuánto se parece a todas las
consultas), y reordenado con el léxico (TF-IDF de lemas). Solo cuenta un
tercero que supera el 99,5 % de los pares al azar y comparte al menos dos
términos con la consulta; si ninguno lo hace, ese modo queda vacío. Para cada tercero se dice hacia qué tirada se inclina (su puntaje
contra lo propio de cada una).

Además, lo común de todos los pares se agrupa en núcleos (k-means sobre el
espacio estructural; k por silueta): cada núcleo con su peso (pares y peso
compartido), sus términos y su propio tercero.

Terceros posibles: los PDF del corpus y los textos publicados en la
plataforma, menos Aire, Embriaguez y Lie, Lay, Ley (el mismo cuerpo).

Usa lo que calcula cutup.py (lo importa y lo corre). Escribe
sitio/tercero.json, que lee sitio/tercero.html.
"""
import contextlib, io, json, math, collections, random
import numpy as np

with contextlib.redirect_stdout(io.StringIO()):
    import cutup as C

random.seed(3); np.random.seed(3)
A, B = C.A, C.B
VID, E, CUENTA, idf = C.VID, C.E, C.CUENTA, C.idf
V, IDS, SIT = C.V, C.IDS, C.SIT
_ps = C._ps
TIT = C.TIT

# ── el espacio estructural, el mismo que usan los pasajes en cutup.py ──
CENTRO = C.CENTRO
Vt = C.Vt


def estructural(w):
    """Vector estructural de una consulta {término: peso}."""
    v = sum((E[VID[c]] * x for c, x in w.items() if c in VID), np.zeros(E.shape[1], dtype=np.float32))
    if not np.any(v):
        return None
    v = v / (np.linalg.norm(v) + 1e-9)
    for k in range(3):
        v = v - ((v - CENTRO) @ Vt[k]) * Vt[k]
    v = v - CENTRO
    return v / (np.linalg.norm(v) + 1e-9)


def norma(w):
    n = math.sqrt(sum(x * x for x in w.values())) or 1
    return {c: x / n for c, x in w.items()}


# ── terceros posibles ──
def es_candidato(i):
    s = SIT[i]
    if s in C.FAM:
        return False
    p = _ps[IDS[i]]
    if p.get('tipo_nodo') == 'pdf':
        return True
    return bool(C.META.get(s, {}).get('publicado'))  # escritos: solo los publicados


CAND = np.array([i for i in range(len(IDS)) if es_candidato(i)])
VC = V[CAND]
LEX = {}


def lex(i):
    if i not in LEX:
        LEX[i] = C.tfidf(IDS[i])
    return LEX[i]


def cos_lex(q, d):
    return sum(x * d.get(c, 0) for c, x in q.items())


# Corrección de «hubs»: algunos pasajes quedan cerca de casi todo en el
# espacio estructural y saldrían como tercero de cualquier par. Se usa CSLS
# (cross-domain similarity local scaling): 2·cos(q, d) − r(q) − r(d), donde
# r(d) es el coseno medio de d con sus 10 consultas más cercanas (cuán «hub»
# es) y r(q) el de la consulta con sus 10 candidatos más cercanos. Se fija
# abajo, cuando están todas las consultas (HUB).
HUB = None
KVEC = 10


def buscar(w, k=3, excluir_sitios=()):
    """Los k mejores terceros para la consulta w (términos → peso), con la
    corrección de hubs; solo los que superan al azar (UMBRAL) y comparten
    al menos dos términos con la consulta."""
    v = estructural(w)
    if v is None:
        return []
    s = VC @ v
    rq = float(np.mean(np.sort(s)[-KVEC:]))
    csls = 2 * s - rq - HUB
    top = np.argsort(-csls)[:80]
    q = norma(w)
    res = []
    for t in top:
        i = int(CAND[t])
        if SIT[i] in excluir_sitios or csls[t] < UMBRAL:
            continue
        d = lex(i)
        compartidos = sum(1 for c in q if c in d)
        if compartidos < 2:
            continue
        lx = cos_lex(q, d)
        res.append((float(csls[t]) + 0.5 * lx, i, float(s[t]), lx, float(csls[t])))
    res.sort(key=lambda x: -x[0])
    out, vistos = [], set()
    for r in res:
        if SIT[r[1]] in vistos:  # un tercero por obra
            continue
        vistos.add(SIT[r[1]])
        out.append(r)
        if len(out) == k:
            break
    return out


def fuerza(c):
    """Cuántas desviaciones por encima del azar (z contra los pares al azar)."""
    return round((c - float(NULO.mean())) / float(NULO.std()), 1)


# ── pares de páginas gemelas ──
LA, LB = C.LA, C.LB
pares = {}
for i, p in enumerate(LA):
    j = int(C.mejorA[i])
    pares[(i, j)] = None
for j, p in enumerate(LB):
    i = int(C.mejorB[j])
    pares[(i, j)] = None

FRAG = {}  # pasajes citados: id → datos para mostrar


def frag(i):
    pid = IDS[i]
    if pid not in FRAG:
        p = _ps[pid]; s = SIT[i]; m = C.META.get(s, {})
        FRAG[pid] = {'obra': TIT.get(s, s), 'slug': s, 'tipo': p.get('tipo_nodo'), 'pagina': p.get('pdf_pagina'),
                     'pdf': m.get('archivo_pdf'), 'fecha': (C.FECHAS.get(s) or {}).get('punto'),
                     'publicado': bool(m.get('publicado')), 'texto': C.recortar(p['texto'], 420)}
    return pid


def por_que(w, i, k=5):
    d = lex(i)
    return [C.ver(c) for c, _ in sorted(((c, x * d[c]) for c, x in w.items() if c in d), key=lambda x: -x[1])[:k]]


def inclinacion(i, wa, wb):
    v = V[i]
    sa = float(v @ estructural(wa)) if wa and estructural(wa) is not None else 0.0
    sb = float(v @ estructural(wb)) if wb and estructural(wb) is not None else 0.0
    if abs(sa - sb) < 0.03:
        return 'las dos', round(sa, 3), round(sb, 3)
    return ('Aire' if sa > sb else 'Embriaguez'), round(sa, 3), round(sb, 3)


# ── consultas de todos los pares y modos: con ellas se mide cuán «hub» es
# cada candidato, y el azar (consulta de un par contra un candidato
# cualquiera) que fija el umbral ──
def modos_de(i, j):
    va, vb = C.VA[i], C.VB[j]
    com = {c: min(va[c], vb[c]) for c in va if c in vb}
    pa = {c: x for c, x in va.items() if c not in vb}
    pb = {c: x for c, x in vb.items() if c not in va}
    return com, pa, pb, {'común': com, 'común + Embriaguez': {**com, **pb}, 'común + Aire': {**com, **pa},
                         'todo': {**{c: x for c, x in va.items()}, **{c: max(x, va.get(c, 0)) for c, x in vb.items()}}}


QV = []
for (i, j) in sorted(pares):
    for w in modos_de(i, j)[3].values():
        v = estructural(w) if w else None
        if v is not None:
            QV.append(v)
QV = np.array(QV, dtype=np.float32)
SQ = QV @ VC.T                                   # consultas × candidatos
HUB = np.mean(np.sort(SQ, axis=0)[-KVEC:], axis=0)  # r(d)
RQ = np.mean(np.sort(SQ, axis=1)[:, -KVEC:], axis=1)
filas = np.random.randint(len(QV), size=20000); cols = np.random.randint(len(CAND), size=20000)
NULO = np.sort(2 * SQ[filas, cols] - RQ[filas] - HUB[cols])
UMBRAL = float(np.quantile(NULO, 0.995))      # el tercero tiene que estar en el 0,5 % más alto del azar
del SQ

comunes_vec, comunes_key = [], []
salida = {}
for (i, j) in sorted(pares):
    com, pa, pb, modos = modos_de(i, j)
    res = {}
    for nombre, w in modos.items():
        if not w:
            res[nombre] = []
            continue
        r = []
        for sc, k, st, lx, cs in buscar(w):
            inc, sa, sb = inclinacion(k, pa, pb)
            r.append({'id': frag(k), 'puntaje': round(cs, 3), 'fuerza': fuerza(cs), 'estructural': round(st, 3), 'lexico': round(lx, 3),
                      'por': por_que(w, k), 'inclina': inc})
        res[nombre] = r
    key = '%s:%s' % (C.pag(LA[i]), C.pag(LB[j]))
    salida[key] = {'aire': C.pag(LA[i]), 'embriaguez': C.pag(LB[j]), 'coseno': round(float(C.S[i, j]), 3),
                   'clase': C.clase(float(C.S[i, j])),
                   'comun': [C.ver(c) for c, _ in sorted(com.items(), key=lambda x: -x[1])[:12]],
                   'peso_comun': round(sum(com.values()), 3),
                   'solo_aire': [C.ver(c) for c, _ in sorted(pa.items(), key=lambda x: -x[1])[:10]],
                   'solo_embriaguez': [C.ver(c) for c, _ in sorted(pb.items(), key=lambda x: -x[1])[:10]],
                   'terceros': res}
    if C.clase(float(C.S[i, j])) != 'propio':
        v = estructural(com)
        if v is not None:
            comunes_vec.append(v); comunes_key.append((key, com))

# ── núcleos de lo común ──
X = np.array(comunes_vec)


def kmeans(X, k, it=60):
    c = [X[np.random.randint(len(X))]]
    for _ in range(1, k):
        d = np.clip(np.min(np.array([1 - X @ ci for ci in c]), axis=0), 0, None) + 1e-9
        c.append(X[np.random.choice(len(X), p=d / d.sum())])
    c = np.array(c)
    for _ in range(it):
        lab = np.argmax(X @ c.T, axis=1)
        nc = np.array([X[lab == g].mean(0) if np.any(lab == g) else c[g] for g in range(k)])
        nc /= np.linalg.norm(nc, axis=1, keepdims=True) + 1e-9
        if np.allclose(nc, c):
            break
        c = nc
    return lab, c


def silueta(X, lab):
    idx = np.random.choice(len(X), min(400, len(X)), replace=False)
    D = 1 - X[idx] @ X.T
    s = []
    for r, i in enumerate(idx):
        own = lab == lab[i]
        a = D[r][own].sum() / max(1, own.sum() - 1)
        b = min(D[r][lab == g].mean() for g in set(lab) if g != lab[i])
        s.append((b - a) / max(a, b))
    return float(np.mean(s))


mejor = None
for k in range(5, 15):
    lab, cen = kmeans(X, k)
    if len(set(lab)) < k:
        continue
    sil = silueta(X, lab)
    if mejor is None or sil > mejor[0]:
        mejor = (sil, k, lab, cen)
sil, K, LAB, CEN = mejor
nucleos = []
for g in range(K):
    miembros = [n for n in range(len(comunes_key)) if LAB[n] == g]
    w = collections.Counter()
    for n in miembros:
        for c, x in comunes_key[n][1].items():
            w[c] += x
    if not w:
        continue
    peso = sum(salida[comunes_key[n][0]]['peso_comun'] for n in miembros)
    fuerte = max(miembros, key=lambda n: float(X[n] @ CEN[g]))
    terceros = []
    for sc, k2, st, lx, cs in buscar(dict(w.most_common(40))):
        terceros.append({'id': frag(k2), 'puntaje': round(cs, 3), 'fuerza': fuerza(cs), 'por': por_que(dict(w.most_common(40)), k2)})
    nucleos.append({'nucleo': ' · '.join(C.ver(c) for c, _ in w.most_common(3)), 'terminos': [C.ver(c) for c, _ in w.most_common(12)],
                    'pares': len(miembros), 'peso': round(peso, 2), 'par_central': comunes_key[fuerte][0],
                    'miembros': [comunes_key[n][0] for n in miembros], 'terceros': terceros})
nucleos.sort(key=lambda x: -x['peso'])
for n, nu in enumerate(nucleos):
    for key in nu['miembros']:
        salida[key]['nucleo'] = n

json.dump({'descripcion': 'Experimento «tercero»: para cada par de páginas gemelas de Aire en la cuerda y De embriaguez y pathos, '
                          'el fragmento de un tercer texto con el que se relacionan, por lo común, por lo propio de cada tirada o por '
                          'todo. Lo arma a mano sitio/matriz/anexo/scripts/tercero.py.',
           'modos': ['común', 'común + Embriaguez', 'común + Aire', 'todo'],
           'aire': {'slug': A, 'titulo': TIT.get(A), 'pdf': C.META[A].get('archivo_pdf')},
           'embriaguez': {'slug': B, 'titulo': TIT.get(B), 'pdf': C.META[B].get('archivo_pdf')},
           'umbral': {'csls': round(UMBRAL, 3), 'percentil_azar': 99.5, 'z': fuerza(UMBRAL), 'terminos_compartidos': 2},
           'silueta': round(sil, 3), 'nucleos': nucleos, 'pares': salida, 'fragmentos': FRAG,
           # desde qué par se lee cada página (la página y su gemela)
           'por_aire': {str(C.pag(LA[i])): '%s:%s' % (C.pag(LA[i]), C.pag(LB[int(C.mejorA[i])])) for i in range(len(LA))},
           'por_embriaguez': {str(C.pag(LB[j])): '%s:%s' % (C.pag(LA[int(C.mejorB[j])]), C.pag(LB[j])) for j in range(len(LB))}},
          open(C.RAIZ + 'sitio/tercero.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('pares', len(salida), '| núcleos', K, 'silueta', round(sil, 3), '| fragmentos', len(FRAG))
for nu in nucleos:
    print(' ', nu['pares'], nu['peso'], nu['nucleo'], '→', [FRAG[t['id']]['obra'] for t in nu['terceros']])
ej = salida[nucleos[0]['par_central']]
print('ejemplo', nucleos[0]['par_central'], {m: [(FRAG[t['id']]['obra'], FRAG[t['id']]['pagina'], t['inclina']) for t in r] for m, r in ej['terceros'].items()})
