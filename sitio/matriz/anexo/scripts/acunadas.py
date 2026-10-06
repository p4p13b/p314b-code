"""Palabras raras (acuñaciones) que caen en el contexto de cada núcleo en
obras de series distintas: la palabra que emerge del clúster en diagonal."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, pickle, collections, math, re, sys
from lematica import tokens, norm
from estructural_semillas import marcar, SEMILLAS

from claves import meta_por_clave
P = json.load(open(RAIZ + 'cache-matriz/pasajes.json')); META = meta_por_clave(P)  # por obra_clave o por sitio
R = json.load(open('nucleos_lematicos.json'))
K = json.load(open('consenso.json'))['nucleos']
CORP = pickle.load(open('corpus.pkl', 'rb'))
formas = collections.defaultdict(collections.Counter)
for c, f in CORP['formas_de'].items():
    formas['sí' if c == 'sí' else norm(c)].update(f)


def serie(o):
    m = re.search(r'txt/([^/]+)-txt', META.get(o, {}).get('fuente', ''))
    return m.group(1) if m else 'posteos'


from duplicados import ids_fuera
FUERA_ = ids_fuera()
docs = []
for p in P['pasajes']:
    if p['id'] in FUERA_:
        continue
    docs.append((p, [c if c == 'sí' else norm(c) for _, c in tokens(marcar(p['texto']))]))
frec = collections.Counter(); obras = collections.defaultdict(set)
for p, cl in docs:
    frec.update(cl)
    for c in cl:
        obras[c].add(p['obra_clave'])
TOT = sum(frec.values())
VENT = 15
# ¿es palabra de diccionario? aproximación: el modelo de spaCy la conoce con vector
try:
    import spacy
    nlp = spacy.load('es_core_news_lg', disable=['parser', 'ner', 'tagger', 'lemmatizer', 'attribute_ruler', 'morphologizer'])
    def conocida(w):
        return nlp.vocab.has_vector(w) and nlp.vocab[w].rank < 200000 if hasattr(nlp.vocab[w], 'rank') else nlp.vocab.has_vector(w)
except Exception:
    def conocida(w):
        return True

raras = {c for c, n in frec.items() if 2 <= n <= 60 and len(obras[c]) >= 2 and len(c) >= 6}
todas_sem = set().union(*SEMILLAS.values())
salida = []
for nu, info in zip(K, R):
    m = set(nu['miembros'])
    base = sum(frec[c] for c in m) / TOT  # probabilidad de un miembro por token
    af = collections.Counter(); ven = collections.Counter(); obr = collections.defaultdict(set); ej = {}
    for p, cl in docs:
        for i, c in enumerate(cl):
            if c in raras and c not in m and c not in todas_sem:
                w = cl[max(0, i - VENT): i + VENT + 1]
                h = sum(1 for x in w if x in m)
                ven[c] += len(w); af[c] += h
                if h:
                    obr[c].add(p['obra_clave'])
                    if c not in ej or h > ej[c][0]:
                        ej[c] = (h, p['obra_clave'], p.get('pdf_pagina'))
    cand = []
    for c in af:
        if len(obr[c]) < 2:
            continue
        lift = (af[c] / ven[c]) / base
        series = {serie(o) for o in obr[c]}
        forma = formas[c].most_common(1)[0][0] if formas.get(c) else c
        nueva = not conocida(forma)
        cand.append({'c': forma, 'lift': round(lift, 1), 'n': frec[c], 'obras_ctx': sorted(META[o]['titulo'] for o in obr[c]),
                     'series': sorted(series), 'acunada': nueva,
                     'score': round(lift * math.log1p(af[c]) * (1 + 0.5 * (len(series) - 1)) * (1.5 if nueva else 1), 1)})
    cand.sort(key=lambda x: -x['score'])
    salida.append({'nucleo': info['palabra'], 'raras': cand[:15]})
    print(f"\n[{info['palabra'].upper()}]")
    for x in cand[:12]:
        print(f"  {x['c']:22s} {'*' if x['acunada'] else ' '} lift={x['lift']:5.1f} n={x['n']:3d} series={len(x['series'])} {x['obras_ctx'][:5]}")
json.dump(salida, open('acunadas.json', 'w'), ensure_ascii=False, indent=1)
