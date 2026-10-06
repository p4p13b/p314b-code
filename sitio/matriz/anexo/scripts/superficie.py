"""Superficie relacional: el índice que usa el taller para leer un texto nuevo
contra todo el cuerpo. Lo corre correr.sh (a mano o el workflow
«Superficie»), nunca la plataforma. Escribe sitio/matriz/superficie/:

  lexico.json    claves (lemas), cuántas obras usan cada una, y para las
                 frecuentes: idf, primera fecha, vecinos estructurales (fase 2),
                 núcleo, si es nodo convergente (fase 5), peso en el léxico
                 de +0, si es léxico lírico
  pasajes.json   cada pasaje (sin los repetidos entre libros): obra, fecha
                 estimada (cronología de la autora, interpolada dentro de la
                 obra), página o capítulo, un fragmento y sus 20 claves de
                 mayor tf-idf, intercaladas con su peso en centésimos
  perfil.json    núcleos (fase 2), atractores por período y nodos
                 convergentes con su vecindario por período (fase 5),
                 operadores de relación con su línea de base por período,
                 el modelo de las dos firmas de +0 (fase 4), las diagonales
                 que la autora ya tendió (lo reconocido por uso) y las obras

La lematización es la de la página (diagonal.js + lemas.json +
lemas-auto.json): el taller tiene que lematizar igual para comparar.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
from fechas_base import anio_de
import json, math, os, re, pickle, collections, datetime as dt
import numpy as np
from lematica import tokens, norm
from duplicados import ids_fuera
import criterios_base as cb

SALIDA = os.path.join(RAIZ, 'sitio', 'matriz', 'superficie')
os.makedirs(SALIDA, exist_ok=True)
P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
META = P['meta']['sitios']
FECHAS = json.load(open('fechas.json'))
EST = json.load(open('estructural.json'))
CONS = json.load(open('consenso.json'))
NUC = json.load(open('nucleos_lematicos.json'))
VEC = json.load(open('vectores.json'))
GEN = json.load(open('genealogia.json'))
CORP = pickle.load(open('corpus.pkl', 'rb'))
FUERA = ids_fuera()


anio = anio_de


# ── pasajes con fecha ──
por_obra = collections.defaultdict(list)
for p in P['pasajes']:
    if p['id'] not in FUERA:
        por_obra[p['obra_clave']].append(p)
pas = []
for o, ps in por_obra.items():
    f = FECHAS.get(o, {})
    a, b = (anio(f['desde']), anio(f['hasta'])) if f.get('desde') else (None, None)
    for i, p in enumerate(ps):
        claves = [c if c == 'sí' else norm(c) for _, c in tokens(p['texto'])]
        fecha = round(a + (b - a) * (i + .5) / len(ps), 3) if a is not None else None
        pas.append({'p': p, 'o': o, 'f': fecha, 'k': claves})
print(len(pas), 'pasajes', flush=True)

# ── vocabulario ──
df = collections.Counter(); frec = collections.Counter(); obras_de = collections.defaultdict(set); primera = {}
for x in pas:
    frec.update(x['k'])
    for c in set(x['k']):
        df[c] += 1; obras_de[c].add(x['o'])
        if x['f'] is not None and (c not in primera or x['f'] < primera[c]):
            primera[c] = x['f']
N = len(pas)
idf = {c: math.log(N / d) for c, d in df.items()}

# claves con información completa (frecuentes)
RICAS = sorted([c for c, n in frec.items() if n >= 5 and len(c) >= 3], key=lambda c: -frec[c])
IDX = {c: i for i, c in enumerate(RICAS)}

# vecinos estructurales (fase 2: PPMI + SVD)
VOC = EST['voc']; VID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy').astype(np.float32)
GENERICAS = __import__('clusters_base').GENERICAS
vecinos = {}
cand = [c for c in RICAS if c in VID]
M = E[[VID[c] for c in cand]]
for i0 in range(0, len(cand), 800):
    S = M[i0:i0 + 800] @ E.T
    for j, c in enumerate(cand[i0:i0 + 800]):
        orden = np.argsort(-S[j])[:14]
        vecinos[c] = [VOC[k] for k in orden if VOC[k] != c and VOC[k] in IDX and VOC[k] not in GENERICAS][:6]
print('vecinos listos', flush=True)

# núcleos (fase 2), convergentes (fase 5), léxico de +0 (fase 4), lírico
NUCLEOS = []
for n, info in zip(CONS['nucleos'], NUC):
    NUCLEOS.append({'palabra': info['palabra'], 'clave': n['palabra'], 'miembros': n['miembros'], 'semillas': info['semillas'],
                    'consenso': n['consenso']})
fase2 = json.load(open(os.path.join(RAIZ, 'sitio', 'matriz', 'anexo', 'datos', 'fase2-nucleos.json')))
for n, n2 in zip(NUCLEOS, fase2['nucleos']):
    n['acunada'] = n2['acunada']['palabra']
nucleo_de = {}
for i, n in enumerate(NUCLEOS):
    for m in n['miembros']:
        nucleo_de[m] = i
CONV = VEC['nodos']
conv_de = {n['nodo']: i for i, n in enumerate(CONV)}
LEX = GEN['modelo_firma']['LEX']
# el núcleo lírico es el que tiene eterno/eterna/eternidad (su nombre cambia con la lematización)
LIRICO = set(next((n['miembros'] for n in CONS['nucleos'] if any(m.startswith('etern') for m in [n['palabra']] + n['miembros'])), [])) | {
    'alma', 'eternidad', 'eterno', 'soledad', 'muerte', 'vida', 'cielo', 'noche', 'luz', 'amor', 'sangre', 'dios',
    'espiritu', 'mar', 'tierra', 'fuego', 'llanto', 'dolor', 'sueño', 'silencio', 'lagrima', 'rosa', 'luna', 'sol'}

# forma de superficie más frecuente (para mostrar)
FORMAS = collections.defaultdict(collections.Counter)
for c, f in CORP['formas_de'].items():
    FORMAS['sí' if c == 'sí' else norm(c)].update(f)

lexico = {'claves': RICAS,
          'forma': [FORMAS[c].most_common(1)[0][0] if FORMAS.get(c) else c for c in RICAS],
          'idf': [round(idf[c], 2) for c in RICAS],
          'obras': [len(obras_de[c]) for c in RICAS],
          'primera': [primera.get(c) for c in RICAS],
          'vecinos': [[IDX[v] for v in vecinos.get(c, [])] for c in RICAS],
          'nucleo': {IDX[c]: i for c, i in nucleo_de.items() if c in IDX},
          'convergente': {IDX[c]: i for c, i in conv_de.items() if c in IDX},
          'mas0': {IDX[c]: w for c, w in LEX.items() if c in IDX},
          'lirico': [IDX[c] for c in LIRICO if c in IDX],
          # todas las demás claves del cuerpo, solo con cuántas obras las usan
          # (para saber si una palabra del texto nuevo es del cuerpo o nueva)
          'raras': {c: len(obras_de[c]) for c in frec if c not in IDX}}

# ── pasajes: fragmento y 24 claves de mayor tf-idf ──
TIT = {o: m['titulo'] for o, m in META.items()}
pasajes = []
for x in pas:
    tf = collections.Counter(c for c in x['k'] if c in IDX)
    if not tf:
        continue
    pes = {c: (1 + math.log(n)) * idf[c] for c, n in tf.items()}
    top = sorted(pes.items(), key=lambda kv: -kv[1])[:20]
    norma = math.sqrt(sum(w * w for _, w in top)) or 1
    p = x['p']
    pasajes.append({'id': p['id'], 'o': x['o'], 'f': x['f'], 'pg': p.get('pdf_pagina'), 'cap': p.get('capitulo'),
                    't': re.sub(r'\s+', ' ', p['texto'])[:220],
                    # claves y pesos intercalados, peso en centésimos: [i, w, i, w…]
                    'k': [v for c, w in top for v in (IDX[c], round(100 * w / norma))]})

# ── operadores de relación y su línea de base por período ──
OPERADORES = {
    'negación': r'\b(no|ni|nunca|jamás|nada|nadie|ningún|ninguna|ninguno|sin|tampoco)\b',
    'mismidad / identidad': r'\b(mismo|misma|mismos|mismas|mismidad|idéntico|idéntica|igual|iguales|igualdad|identidad)\b',
    'semejanza': r'\b(como|semejante|semejantes|semejanza|símil|parecido|parecida|análogo|análoga)\b',
    'equivalencia': r'\b(equivale|equivalen|equivaler|equivalente|equivalentes|equivalencia|es decir|o sea)\b',
    'modalidad': r'\b(posible|posibles|imposible|imposibles|necesario|necesaria|necesidad|contingente|puede|pueden|podría|debe|deben|quizás|acaso)\b',
    'disyunción': r'\b(o|u)\b',
    'dosidad / alteridad': r'\b(dos|otro|otra|otros|otras|ambos|ambas|par|entre)\b',
    'condición / inferencia': r'\b(si|entonces|luego|ende|porque|pues|dado que|por lo tanto)\b',
    'cuantificación': r'\b(todo|toda|todos|todas|cada|uno|una|cero|infinito|infinita|cantidad)\b',
}
V = pickle.load(open('ventanas.pkl', 'rb'))
textos = {}
for s, m in META.items():
    f = m.get('fuente', '')
    textos[s] = cb.texto_post(f) if f.endswith('.json') else cb.texto_pdf(f)


def periodo(v):
    if v['carpeta'] == 'VI - +0':
        return '+0'
    if v['obra'] == 'terminos-y-condiciones':
        return 'TyC'
    if v['t'] < 2020:
        return '2017-19'
    if v['t'] < 2023:
        return '2020-22'
    return None if v['carpeta'] == 'en curso (sin carpeta)' else '2023-25'


tasas = collections.defaultdict(lambda: collections.defaultdict(list))
for v in V:
    per = periodo(v)
    if not per:
        continue
    seg = textos[v['obra']][v['x']:v['y']].lower()
    nw = len(re.findall(r"[^\W\d_]+", seg)) or 1
    for nom, rx in OPERADORES.items():
        tasas[nom][per].append(1000 * len(re.findall(rx, seg)) / nw)
operadores = {nom: {'rx': rx, 'base': {per: [round(float(np.mean(xs)), 1), round(float(np.std(xs)), 1)] for per, xs in d.items()}}
              for nom, rx in OPERADORES.items() for d in [tasas[nom]]}

conv = [{'nodo': n['nodo'], 'forma': FORMAS[n['nodo']].most_common(1)[0][0] if FORMAS.get(n['nodo']) else n['nodo'],
         'tipo': n['tipo'], 'primera': n['primera'], 'base': n['base'], 'TyC': n['TyC'], '+0': n['+0'],
         'vecinos': n['vecinos']} for n in CONV]
# ── lo que la autora ya reconoce: sus diagonales confirmadas ──
# Para que la superficie distinga lo que ya se relaciona por uso (una
# diagonal tendida) de lo que aparece nuevo.
import sys
sys.path.insert(0, os.path.join(RAIZ, 'sitio', 'matriz'))
import comun  # noqa: E402
ACC = (comun.cargar_json(comun.ACCIONES_PATH, {'acciones': {}}).get('acciones') or {})
reconocidas = []
for d in comun.diagonales_confirmadas():
    t = d.get('tipo') or {}
    dest = (ACC.get(t.get('destino')) or {}).get('origen') or {}
    ks = set()
    for w in (t.get('lemas') or []) + [t.get('instrumento_lema') or '', t.get('instrumento_nuevo_label') or t.get('titulo') or '']:
        ks.update(c if c == 'sí' else norm(c) for _, c in tokens(w.replace('-', ' ')))
    reconocidas.append({'titulo': t.get('instrumento_nuevo_label') or t.get('titulo') or t.get('instrumento'),
                        'relacion': t.get('tipo_relacion'),
                        'obras': sorted({o for o in ((d.get('origen') or {}).get('obra'), dest.get('obra')) if o}),
                        'claves': sorted(ks)})

# cómo se llama cada obra en el taller (obras/<id>.json, corpus.json): los PDF
# pueden tener otro id que el del índice (sí teoría → si-teoria-pdf, 1021 → 1-0-2-1)
CORPUS = json.load(open(os.path.join(RAIZ, 'sitio', 'corpus.json'))).get('obras', [])
en_taller = {}
for x in CORPUS:
    if x.get('_pdfArchivo'):
        en_taller.setdefault(('pdf', x['_pdfArchivo']), x)
    en_taller.setdefault(('id', x['id']), x)


def del_taller(o):
    m = META[o]
    return (m.get('archivo_pdf') and en_taller.get(('pdf', m['archivo_pdf']))) or en_taller.get(('id', o))


obras = {}
for o in META:
    t = del_taller(o) or {}
    obras[o] = {'titulo': TIT[o], 'carpeta': FECHAS.get(o, {}).get('carpeta'), 'archivo': META[o].get('archivo_pdf'),
                'tipo': META[o].get('tipo_nodo'), 'taller': t.get('id'), 'html': t.get('_file'),
                'publicado': bool(t.get('_file') and os.path.exists(os.path.join(RAIZ, 'sitio', 'obras', t['_file'].rsplit('.', 1)[0] + '.json')))}
perfil = {'generado': dt.date.today().isoformat(), 'pasajes': len(pasajes), 'claves': len(RICAS),
          'nucleos': NUCLEOS, 'atractores': VEC['atractores'], 'convergentes': conv, 'lirico_base': VEC['lirico_base'],
          'operadores': operadores, 'reconocidas': reconocidas, 'firma': GEN['modelo_firma'],
          'firma_por_carpeta': {'formal': GEN['formal']['por_carpeta'], 'lexica': GEN['lexica']['por_carpeta']},
          'obras': obras,
          # la lematización del taller tiene que ser idéntica a lematica.py
          'lematizacion': {'vacias': sorted(__import__('lematica').VACIAS), 'extra': sorted(__import__('lematica').EXTRA)}}

for nombre, data in (('lexico.json', lexico), ('pasajes.json', pasajes), ('perfil.json', perfil)):
    with open(os.path.join(SALIDA, nombre), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(nombre, round(os.path.getsize(os.path.join(SALIDA, nombre)) / 1e6, 2), 'MB')
