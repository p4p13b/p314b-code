"""Modelo estructural (paradigmático): palabras que ocupan el mismo lugar que
la semilla, en otras obras, de forma estable entre mitades disjuntas del
cuerpo. Después, clústeres estables y la palabra de cada clúster."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, collections, math, random, sys
import numpy as np
import networkx as nx
from lematica import tokens, norm

P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
META = P['meta']['sitios']
VENT = 6
DIM = 256

MARCAS = [
    (re.compile(r'(?<=[a-záéíóúñ,;]\s)Nadie\b'), 'NADIECONCEPTO'),       # Nadie con mayúscula a mitad de frase
    (re.compile(r'\b(el|del|al|su|un|ese|este|propio|mi|tu|sus|los|cada)\s+sí\b', re.I), r'\1 SICONCEPTO'),
]


def marcar(t):
    for rx, rep in MARCAS:
        t = rx.sub(rep, t)
    return t


def serie(obra):
    f = META.get(obra, {}).get('fuente', '')
    m = re.search(r'txt/([^/]+)-txt', f)
    return m.group(1) if m else 'posteos'


from duplicados import ids_fuera
FUERA_ = ids_fuera()
docs = []
for p in P['pasajes']:
    if p['id'] in FUERA_:
        continue
    cl = [c if c == 'sí' else norm(c) for _, c in tokens(marcar(p['texto']))]
    docs.append((p['obra_clave'], cl, p['id']))
OBRAS = sorted({o for o, _, _ in docs})

frec = collections.Counter()
obras_de = collections.defaultdict(collections.Counter)
for o, cl, _ in docs:
    frec.update(cl)
    for c in cl:
        obras_de[c][o] += 1
VOC = [c for c, n in frec.items() if n >= 8 and len(obras_de[c]) >= 3]
ID = {c: i for i, c in enumerate(VOC)}
CTX = [c for c, _ in frec.most_common() if c in ID][:5000]
CID = {c: i for i, c in enumerate(CTX)}
print('vocabulario', len(VOC), 'contextos', len(CTX), file=sys.stderr)


def modelo(obras_incluidas):
    """Embeddings PPMI+SVD con los pasajes de esas obras."""
    rows, cols = [], []
    for o, cl, _ in docs:
        if o not in obras_incluidas:
            continue
        t = np.array([ID.get(c, -1) for c in cl])
        x = np.array([CID.get(c, -1) for c in cl])
        for d in range(1, VENT + 1):
            if len(t) <= d:
                break
            a, b = t[:-d], x[d:]
            m = (a >= 0) & (b >= 0)
            rows.append(a[m]); cols.append(b[m])
            a, b = t[d:], x[:-d]
            m = (a >= 0) & (b >= 0)
            rows.append(a[m]); cols.append(b[m])
    r = np.concatenate(rows); c = np.concatenate(cols)
    M = np.zeros((len(VOC), len(CTX)), dtype=np.float32)
    np.add.at(M, (r, c), 1)
    tot = M.sum()
    pw = M.sum(1, keepdims=True) / tot
    pc = M.sum(0, keepdims=True) ** 0.75
    pc = pc / pc.sum()
    with np.errstate(divide='ignore', invalid='ignore'):
        PM = np.log((M / tot) / (pw * pc))
    PM[~np.isfinite(PM)] = 0
    PM[PM < 0] = 0
    U, S, _ = np.linalg.svd(PM, full_matrices=False)
    E = U[:, :DIM] * np.sqrt(S[:DIM])
    E /= (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    presentes = M.sum(1) > 0
    return E, presentes


SEMILLAS = {
    'Nadie': {'nadieconcepto', 'nadidad', 'nadiedad', 'nadico', 'nadica', 'nadieca', 'nadieco', 'nadismo'},
    'mismidad': {'mismidad', 'mismidades', 'mismizar', 'mismizacion', 'mismica', 'mismico', 'mismeidad', 'mismizarse'},
    'indiferir': {'indiferir', 'indiferirse', 'indiferibl', 'indiferibilidad'},
    'discernir': {'discernir', 'discernimiento', 'indiscernible', 'indiscernibilidad', 'indiscernibl'},
    'identidad': {'identidad', 'identico', 'identica', 'identitar', 'identitario'},
    'objetivar': {'objetivar', 'objetivacion', 'objetividad', 'objetivable'},
    'instrumental': {'instrumental', 'instrumentacion', 'instrumentalidad', 'instrumentabilidad', 'instrumentalizacion'},
    'devenir': {'devenir', 'devin', 'devino', 'deviniente', 'deven', 'devenirse'},
    'el sí': {'siconcepto'},
    'Rimbaud': {'rimbaud', 'pagano', 'pagana', 'nobleza', 'mueca'},
}
for s, fam in SEMILLAS.items():
    SEMILLAS[s] = {c for c in fam if c in ID}
    print(s, sorted(SEMILLAS[s]), file=sys.stderr)
TODAS = set().union(*SEMILLAS.values())


def vec_semilla(E, fam, pres):
    ids = [ID[c] for c in fam if pres[ID[c]]]
    if not ids:
        return None
    w = np.array([math.log1p(frec[VOC[i]]) for i in ids])
    v = (E[ids] * w[:, None]).sum(0)
    return v / (np.linalg.norm(v) + 1e-9)


# ── modelo completo ──
E, pres = modelo(set(OBRAS))
print('modelo completo listo', file=sys.stderr)

# ── mitades disjuntas de obras (estabilidad) ──
B = int(sys.argv[1]) if len(sys.argv) > 1 else 6
rng = random.Random(314)
mitades = []
for b in range(B):
    oo = OBRAS[:]
    rng.shuffle(oo)
    A = set(oo[: len(oo) // 2])
    for lado in (A, set(OBRAS) - A):
        mitades.append(modelo(lado))
    print('mitad', b, file=sys.stderr)

K = 60
salida = {}
for s, fam in SEMILLAS.items():
    v = vec_semilla(E, fam, pres)
    sims = E @ v
    obras_sem = collections.Counter()
    for c in fam:
        obras_sem.update(obras_de[c])
    orden = [i for i in np.argsort(-sims) if VOC[i] not in TODAS][:K]
    # estabilidad: en cuántas mitades el candidato queda entre los 150 más cercanos a la semilla
    estab = collections.Counter()
    validas = 0
    for Eh, ph in mitades:
        vh = vec_semilla(Eh, fam, ph)
        if vh is None:
            continue
        validas += 1
        sh = Eh @ vh
        sh[~ph] = -1
        top = set(np.argsort(-sh)[:150])
        for i in orden:
            if i in top:
                estab[i] += 1
    cands = []
    for i in orden:
        c = VOC[i]
        tot_c = sum(obras_de[c].values())
        # discontinuidad: parte de sus ocurrencias en obras donde la semilla no está (o casi)
        fuera = sum(n for o, n in obras_de[c].items() if obras_sem.get(o, 0) < 2)
        cands.append({'c': c, 'sim': round(float(sims[i]), 3), 'estab': round(estab[i] / max(1, validas), 2),
                      'n': tot_c, 'obras': len(obras_de[c]), 'fuera': round(fuera / tot_c, 2),
                      'series': sorted({serie(o) for o in obras_de[c]}),
                      'obras_fuera': [o for o, n in obras_de[c].most_common() if obras_sem.get(o, 0) < 2][:6]})
    salida[s] = {'familia': sorted(fam), 'n': sum(obras_sem.values()), 'obras': len(obras_sem),
                 'obras_top': obras_sem.most_common(8), 'candidatos': cands}
    print(f'\n## {s}  ({sum(obras_sem.values())} en {len(obras_sem)} obras)', file=sys.stderr)
    for x in sorted(cands, key=lambda x: -(x['sim'] * (0.3 + x['estab']) * (0.3 + x['fuera'])))[:14]:
        print(f"  {x['c']:18s} sim={x['sim']:.2f} estab={x['estab']:.2f} fuera={x['fuera']:.2f} n={x['n']}/{x['obras']}o {x['obras_fuera'][:3]}", file=sys.stderr)

np.save('E.npy', E)
json.dump({'voc': VOC, 'salida': salida, 'obras_de': {c: dict(obras_de[c]) for c in VOC}}, open('estructural.json', 'w'), ensure_ascii=False)
import pickle
pickle.dump({'mitades': [(m[0].astype(np.float16), m[1]) for m in mitades]}, open('mitades.pkl', 'wb'))
