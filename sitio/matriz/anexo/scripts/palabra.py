"""Para cada núcleo: palabra interna (medoide), palabra emergente (fuera del
núcleo, más cercana al centro, estable en las mitades), formas superficiales,
obras en diagonal y pasajes testigo."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, pickle, collections, math, re, sys
import numpy as np
from lematica import tokens, norm

J = json.load(open('estructural.json')); VOC = J['voc']; ID = {c: i for i, c in enumerate(VOC)}
OB = J['obras_de']
E = np.load('E.npy')
MIT = pickle.load(open('mitades.pkl', 'rb'))['mitades']
K = json.load(open('consenso.json'))
CORP = pickle.load(open('corpus.pkl', 'rb'))
P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
from claves import meta_por_clave
META = meta_por_clave(P)  # por obra_clave o por sitio
from estructural_semillas import SEMILLAS, marcar  # noqa

formas = collections.defaultdict(collections.Counter)
for c, f in CORP['formas_de'].items():
    formas['sí' if c == 'sí' else norm(c)].update(f)


def sup(c):
    if c == 'nadieconcepto':
        return 'Nadie'
    if c == 'siconcepto':
        return 'el sí'
    f = formas.get(c)
    return f.most_common(1)[0][0] if f else c


def serie(o):
    m = re.search(r'txt/([^/]+)-txt', META.get(o, {}).get('fuente', ''))
    return m.group(1) if m else 'posteos'


# pasajes lematizados (con las marcas de concepto)
from duplicados import ids_fuera
FUERA_ = ids_fuera()
docs = []
for p in P['pasajes']:
    if p['id'] in FUERA_:
        continue
    cl = [c if c == 'sí' else norm(c) for _, c in tokens(marcar(p['texto']))]
    docs.append((p, cl))

TODAS = set().union(*SEMILLAS.values())
ANCLA = {'terminos-y-condiciones', 'no-teoria', 'dos-puntos', 'potencial-de-repente-en-carnaval', 'si', 'los-nacidos', 'si-teoria'}
from clusters_base import GENERICAS
FUERA = GENERICAS | {'sí', 'nadieconcepto', 'siconcepto'}
res = []
for nu in K['nucleos']:
    m = nu['miembros']; mi = [ID[c] for c in m]
    cen = E[mi].mean(0); cen /= np.linalg.norm(cen)
    sims = E @ cen
    excl = set(m) | TODAS | FUERA
    cand = [i for i in np.argsort(-sims)[:80] if VOC[i] not in excl and len(OB[VOC[i]]) >= 4][:25]
    # estabilidad de la emergente: rango en cada mitad
    est = collections.Counter()
    for Eh, ph in MIT:
        Eh = Eh.astype(np.float32)
        ok = [i for i in mi if ph[i]]
        if len(ok) < 2:
            continue
        ch = Eh[ok].mean(0); ch /= np.linalg.norm(ch) + 1e-9
        sh = Eh @ ch; sh[~ph] = -1
        for i in mi:
            sh[i] = -1
        top = set(np.argsort(-sh)[:30])
        for i in cand:
            if i in top:
                est[i] += 1
    emerg = sorted(cand, key=lambda i: -(sims[i] * (0.2 + est[i] / len(MIT))))[:6]
    # semillas del núcleo y sus obras
    sem = [s for s, _ in nu['semillas']]
    obras_sem = collections.Counter()
    for s in sem:
        for c in SEMILLAS[s]:
            obras_sem.update(OB.get(c, {}))
    # densidad del núcleo por obra (ocurrencias por 1000 palabras de contenido)
    largo = collections.Counter(); hits = collections.Counter()
    setm = set(m)
    testigos = []
    for p, cl in docs:
        o = p['obra_clave']; largo[o] += len(cl)
        h = [c for c in cl if c in setm]
        hits[o] += len(h)
        dist = set(h)
        if len(dist) >= 3:
            testigos.append((len(dist), o, p, sorted(dist)))
    dens = {o: 1000 * hits[o] / largo[o] for o in largo if largo[o] > 300}
    glob = 1000 * sum(hits.values()) / sum(largo.values())
    diag = sorted([o for o in dens if o not in ANCLA and hits[o] >= 3 and dens[o] >= glob], key=lambda o: -dens[o])
    casa = sorted([o for o in dens if o in ANCLA and hits[o] >= 2], key=lambda o: -dens[o])
    # testigos: los más densos, de obras distintas, priorizando obras en diagonal
    testigos.sort(key=lambda t: (-(t[1] in diag), -t[0]))
    vistos, tsel = set(), []
    for d, o, p, dist in testigos:
        if o in vistos:
            continue
        vistos.add(o)
        tsel.append({'obra': META[o]['titulo'], 'slug': o, 'serie': serie(o), 'pagina': p.get('pdf_pagina'), 'id': p['id'],
                     'miembros': [sup(c) for c in dist], 'diagonal': o in diag, 'ancla': o in ANCLA, 'texto': p['texto']})
        if len(tsel) >= 6:
            break
    x = {'palabra': sup(nu['palabra']), 'clave': nu['palabra'], 'miembros': [sup(c) for c in m], 'consenso': nu['consenso'],
         'cohesion': nu['cohesion'], 'semillas': sem,
         'emergentes': [{'palabra': sup(VOC[i]), 'sim': round(float(sims[i]), 2), 'estab': round(est[i] / len(MIT), 2),
                         'obras': len(OB[VOC[i]])} for i in emerg],
         'casa': [META[o]['titulo'] for o in casa[:8]],
         'diagonal': [{'obra': META[o]['titulo'], 'slug': o, 'serie': serie(o), 'densidad': round(dens[o], 1)} for o in diag[:10]],
         'series_diag': sorted({serie(o) for o in diag}), 'testigos': tsel}
    res.append(x)
    print(f"\n[{x['palabra'].upper()}] ← {', '.join(x['miembros'])}  (semillas: {', '.join(sem)})")
    print('   emergentes:', ', '.join(f"{e['palabra']}({e['sim']},{e['estab']})" for e in x['emergentes']))
    print('   ancla:', ', '.join(x['casa'][:7]))
    print('   diagonal:', ', '.join(f"{d['obra']}[{d['serie']}]{d['densidad']}" for d in x['diagonal'][:8]))
    for t in tsel[:4]:
        print(f"   · {t['obra']} p{t['pagina']} {'(diag)' if t['diagonal'] else ''} {t['miembros']}")
json.dump(res, open('nucleos_lematicos.json', 'w'), ensure_ascii=False, indent=1)
