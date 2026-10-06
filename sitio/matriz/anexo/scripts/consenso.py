"""Núcleos por consenso: pares que caen juntos en ≥60 % de las particiones
(mitades disjuntas × resoluciones × semillas de Louvain)."""
import _rutas  # noqa: F401  (rutas y carpeta de trabajo)
import json, pickle, collections, math, sys, re
import numpy as np
import networkx as nx

J = json.load(open('estructural.json'))
VOC = J['voc']; ID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy')
MIT = pickle.load(open('mitades.pkl', 'rb'))['mitades']
OB = J['obras_de']
from clusters_base import GENERICAS  # noqa

sel = {}
for s, d in J['salida'].items():
    for x in d['candidatos']:
        if x['c'] in GENERICAS or x['estab'] < 0.6 or x['sim'] < 0.3:
            continue
        sel.setdefault(x['c'], {})[s] = x
nodos = sorted(sel); idx = [ID[c] for c in nodos]; n = len(nodos)


def particion(Em, pres, res, semilla):
    X = Em[idx].astype(np.float32); S = X @ X.T
    G = nx.Graph(); G.add_nodes_from(range(n))
    for i in range(n):
        if not pres[idx[i]]:
            continue
        for j in np.argsort(-S[i])[1:9]:
            if pres[idx[j]] and S[i, j] > 0.25:
                G.add_edge(i, int(j), weight=float(S[i, j]))
    lab = np.full(n, -1)
    for k, g in enumerate(nx.community.louvain_communities(G, weight='weight', resolution=res, seed=semilla)):
        for i in g:
            lab[i] = k
    return lab


co = np.zeros((n, n)); cnt = np.zeros((n, n))
for Em, pres in MIT:
    ok = np.array([bool(pres[i]) for i in idx]); both = np.outer(ok, ok)
    for res in (1.0, 1.6, 2.2, 3.0):
        for sem in (7, 31, 314):
            l = particion(Em, pres, res, sem)
            co += (l[:, None] == l[None, :]) & both; cnt += both
C = np.divide(co, cnt, out=np.zeros_like(co), where=cnt > 0)
np.fill_diagonal(C, 1)
S = E[idx] @ E[idx].T

UMBRAL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
G = nx.Graph(); G.add_nodes_from(range(n))
for i in range(n):
    for j in range(i + 1, n):
        if C[i, j] >= UMBRAL:
            G.add_edge(i, j, weight=C[i, j])
nucleos = []
for comp in nx.community.louvain_communities(G, weight='weight', resolution=1.0, seed=1):
    m = sorted(comp)
    if len(m) < 3:
        continue
    cm = C[np.ix_(m, m)]; sm = S[np.ix_(m, m)]
    k = len(m)
    cons = float((cm.sum() - k) / (k * (k - 1)))
    coh = float((sm.sum() - k) / (k * (k - 1)))
    central = {i: float((C[i, m].sum() - 1) / (k - 1)) * float((S[i, m].sum() - 1) / (k - 1)) for i in m}
    orden = sorted(m, key=lambda i: -central[i])
    semillas = collections.Counter()
    for i in m:
        for s in sel[nodos[i]]:
            semillas[s] += 1
    nucleos.append({'palabra': nodos[orden[0]], 'miembros': [nodos[i] for i in orden], 'consenso': round(cons, 2),
                    'cohesion': round(coh, 2), 'semillas': semillas.most_common(),
                    'central': {nodos[i]: round(central[i], 3) for i in orden}})
nucleos.sort(key=lambda x: -(x['consenso'] * x['cohesion'] * math.log1p(len(x['semillas'])) * math.log(len(x['miembros']))))
for x in nucleos:
    print(f"[{x['palabra'].upper()}] consenso={x['consenso']} coh={x['cohesion']} semillas={[s for s, _ in x['semillas']]}\n   {', '.join(x['miembros'])}")
json.dump({'nucleos': nucleos, 'nodos': nodos, 'C': C.round(3).tolist(), 'sel': sel}, open('consenso.json', 'w'), ensure_ascii=False)
