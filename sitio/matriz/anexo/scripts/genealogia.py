"""Fase 4 · gestación. Desde dónde se fue gestando +0.

Cada obra se parte en ventanas del largo de C.1 (se descartan las ventanas
en inglés) y cada ventana se fecha
dentro de su obra: la autora confirmó que dentro de cada libro el orden
sigue la cronología de escritura, así que la ventana i de n cae en
desde + (i + ½)/n · (hasta − desde).

Dos firmas de +0, cada una un eje de 0 (I - Estudio de los blogs,
2017-2019) a 1 (VI - +0):
  formal   los criterios (cq, IIN, Esint, Eg, costo, hiperespecificidad,
           al-menos-dos, TTR, DRI), estandarizados; peso de cada uno =
           diferencia de medias / varianza (LDA diagonal)
  léxica   los lemas propios de +0 (log-odds con prior de Dirichlet de +0
           contra todo lo anterior a agosto 2025)
Con cada firma: en qué fecha el cuerpo empieza a moverse hacia +0 (la
mediana móvil cruza ¼ y ½ del eje y no vuelve a bajar), y qué pasajes
anteriores ya se parecen a +0 (los que superan la media de +0).
También la aparición en el tiempo de los núcleos de la fase 2.

Escribe genealogia.json (carpeta de trabajo).
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
from fechas_base import anio_de
import json, re, math, collections, statistics, datetime as dt
import numpy as np
from lematica import clave, cuenta, norm
from criterios_base import (META, texto_pdf, texto_post, cortes_de_linea, medir_ventana, ventanas, idioma,
                            PL_ES, SG_ES, HUECO)

FECHAS = json.load(open('fechas.json'))
CRIT = json.load(open('criterios.json'))
NUC = json.load(open('consenso.json'))['nucleos']


def dia(s):
    return dt.date.fromisoformat(s)


anio = anio_de


# estándar endógeno y exclusividad (igual que criterios.py, sobre obras enteras)
textos = {}
for s, m in META.items():
    f = m.get('fuente', '')
    textos[s] = texto_post(f) if f.endswith('.json') else texto_pdf(f)
lem_obra = {s: collections.Counter(norm(clave(w)) for w in re.findall(r"[^\W\d_]+", t) if cuenta(w)) for s, t in textos.items()}
en_cuantas = collections.Counter()
for c in lem_obra.values():
    en_cuantas.update(set(c))
ESTANDAR = {w for w, n in en_cuantas.items() if n >= len(lem_obra) / 2}

# ── ventanas fechadas ──
V = []
for s, t in textos.items():
    f = FECHAS.get(s, {})
    if not f.get('desde') or idioma(t) == 'en':
        continue
    a, b = dia(f['desde']), dia(f['hasta'])
    cortes = cortes_de_linea(t) if not META[s].get('fuente', '').endswith('.json') else set(m.start() for m in re.finditer(r'\n(?!\n)', t))
    vs = ventanas(t)
    for i, (x, y) in enumerate(vs):
        seg = t[x:y]
        if idioma(seg) == 'en':  # ventana en inglés dentro de una obra en castellano: sus palabras
            continue             # inflan costo e hiperespecificidad (quedan fuera del estándar)
        m = medir_ventana(seg)
        if not m:
            continue
        ntok = m['T']
        cq = (len(re.findall(r"[^\w\s]+", seg)) + sum(1 for c in cortes if x <= c < y) + len(re.findall(r'\n\s*\n', seg)) + len(HUECO.findall(seg))) / max(1, ntok - 1)
        lem = [norm(clave(w)) for w in re.findall(r"[^\W\d_]+", seg) if cuenta(w)]
        costo = sum(1 for w in lem if w not in ESTANDAR) / max(1, len(lem))
        hiper = sum(1 for w in lem if en_cuantas[w] == 1) / max(1, len(lem))
        pl, sg = len(PL_ES.findall(seg)), len(SG_ES.findall(seg))
        dos = (min(pl, sg) + 1) / (max(pl, sg) + 1)
        fecha = a + (b - a) * ((i + .5) / len(vs))
        V.append({'obra': s, 'titulo': META[s]['titulo'], 'carpeta': f['carpeta'], 'i': i, 'n': len(vs), 'fecha': fecha.isoformat(),
                  't': anio(fecha), 'confianza': f['confianza'], 'x': x, 'y': y, 'lem': lem,
                  'cq': cq, 'IIN': m['IIN'], 'Esint': m['Esint'], 'Eg': m['Eg'], 'TTR': m['TTR'], 'DRI': m['DRI'],
                  'costo': costo, 'hiper': hiper, 'dos': dos})
print(len(V), 'ventanas fechadas', flush=True)

MAS0 = lambda v: v['carpeta'] == 'VI - +0'
TEMPRANO = lambda v: v['carpeta'] == 'I - Estudio' and v['t'] < 2019.9  # la cadena de blogs 2017-2019
ANTES = lambda v: v['t'] < 2025.6 and v['carpeta'] not in ('VI - +0', 'en curso (sin carpeta)')

# ── firma formal (LDA diagonal) ──
K = ['cq', 'IIN', 'Esint', 'Eg', 'costo', 'hiper', 'dos', 'TTR', 'DRI']
X = np.array([[v[k] for k in K] for v in V])
mu, sd = X.mean(0), X.std(0) + 1e-9
Z = (X - mu) / sd
m1 = Z[[MAS0(v) for v in V]].mean(0); m0 = Z[[TEMPRANO(v) for v in V]].mean(0)
var = Z.var(0) + 1e-9
w = (m1 - m0) / var
raw = Z @ w
s0, s1 = raw[[TEMPRANO(v) for v in V]].mean(), raw[[MAS0(v) for v in V]].mean()
for v, r in zip(V, raw):
    v['formal'] = float((r - s0) / (s1 - s0))
pesos_formal = {k: round(float(x), 3) for k, x in zip(K, w / np.abs(w).sum())}

# ── firma léxica (log-odds informativo, Monroe et al.) ──
c1 = collections.Counter(); c0 = collections.Counter()
for v in V:
    if MAS0(v):
        c1.update(v['lem'])
    elif ANTES(v):
        c0.update(v['lem'])
tot = c1 + c0
n1, n0, n = sum(c1.values()), sum(c0.values()), sum(tot.values())
A = 500.0  # masa del prior
z = {}
for wd, f in tot.items():
    if f < 8:
        continue
    a = A * f / n
    d = math.log((c1[wd] + a) / (n1 + A - c1[wd] - a)) - math.log((c0[wd] + a) / (n0 + A - c0[wd] - a))
    var_ = 1 / (c1[wd] + a) + 1 / (c0[wd] + a)
    z[wd] = d / math.sqrt(var_)
LEX = dict(sorted(((wd, sc) for wd, sc in z.items() if sc > 3.0), key=lambda x: -x[1])[:120])
for v in V:
    v['lex_raw'] = sum(LEX.get(wd, 0) for wd in v['lem']) / max(1, len(v['lem']))
l0 = statistics.mean(v['lex_raw'] for v in V if TEMPRANO(v)); l1 = statistics.mean(v['lex_raw'] for v in V if MAS0(v))
for v in V:
    v['lexica'] = (v['lex_raw'] - l0) / (l1 - l0)

# ── mediana móvil y umbrales ──
V.sort(key=lambda v: v['t'])


def movil(clave_, ancho=0.5):
    ts = np.array([v['t'] for v in V]); ys = np.array([v[clave_] for v in V])
    rej = np.arange(math.floor(ts.min() * 4) / 4, ts.max() + .25, .25)
    return [(round(float(g), 2), round(float(np.median(ys[(ts >= g - ancho) & (ts <= g + ancho)])), 3), int(((ts >= g - ancho) & (ts <= g + ancho)).sum()))
            for g in rej if ((ts >= g - ancho) & (ts <= g + ancho)).sum() >= 4]


def cruce(serie, umbral):
    """Primera fecha desde la cual la mediana móvil queda ≥ umbral hasta el final."""
    for i, (g, y, _) in enumerate(serie):
        if all(yy >= umbral for _, yy, _ in serie[i:]):
            return g
    return None


res = {'ventanas': len(V), 'pesos_formal': pesos_formal, 'lexico_mas0': [[wd, round(sc, 1)] for wd, sc in LEX.items()],
       # el modelo de las dos firmas, para aplicarlo a un texto nuevo (superficie relacional)
       'modelo_firma': {'K': K, 'mu': [float(x) for x in mu], 'sd': [float(x) for x in sd], 'w': [float(x) for x in w],
                        's0': float(s0), 's1': float(s1), 'LEX': {wd: round(sc, 3) for wd, sc in LEX.items()},
                        'l0': float(l0), 'l1': float(l1), 'ESTANDAR': sorted(ESTANDAR)}}
for firma in ('formal', 'lexica'):
    serie = movil(firma)
    res[firma] = {'serie': serie, 'cruce_25': cruce(serie, .25), 'cruce_50': cruce(serie, .5),
                  'por_carpeta': {c: round(statistics.median(v[firma] for v in V if v['carpeta'] == c), 3)
                                  for c in dict.fromkeys(v['carpeta'] for v in V)}}
    # pasajes anteriores a +0 que ya se parecen a +0 (superan su media, 1.0)
    proto = sorted((v for v in V if ANTES(v) and v[firma] >= 1.0), key=lambda v: v['t'])
    res[firma]['proto'] = [{'obra': v['titulo'], 'slug': v['obra'], 'fecha': v['fecha'], 'valor': round(v[firma], 2),
                            'ventana': [v['i'] + 1, v['n']], 'confianza': v['confianza'],
                            'texto': re.sub(r'\s+', ' ', textos[v['obra']][v['x']:v['y']])[:600]} for v in proto]

# ── los núcleos de la fase 2 en el tiempo ──
nucleos = {}
for nu in NUC:
    m = set(nu['miembros'])
    dens = [(v['t'], sum(1 for wd in v['lem'] if wd in m) / max(1, len(v['lem'])) * 1000) for v in V]
    ref = statistics.mean(d for t, d in dens if t >= 2025.6) or 1e-9
    ser = []
    for y in range(2017, 2027):
        ds = [d for t, d in dens if y <= t < y + 1]
        if ds:
            ser.append([y, round(statistics.mean(ds), 2)])
    primero = next((round(t, 2) for t, d in dens if d >= ref), None)
    nucleos[nu['palabra']] = {'por_anio': ser, 'densidad_mas0': round(ref, 2), 'primera_ventana_a_nivel_mas0': primero}
res['nucleos'] = nucleos

# ── primera aparición de los términos de +0 a lo largo de la cronología ──
TERMINOS = {
    'al-menos-dos': r'\b(al[- ]menos[- ]dos|por lo menos (?:dos|Dos)|al[- ]menos[- ]2)\b',
    'mismidad': r'\bmismidad', 'mismizar / mismización': r'\bmismiz', 'indiferir': r'\bindif(?:er(?:ir|ido|ida|ible|ibles|ibilidad|irse|irá|iendo|erir)|iere|ieren|iera)',
    'indiscernible': r'\bindiscernib', 'tempo (como concepto)': r'\b(?:el|del|al|su) tempo\b', 'quantum': r'\bquantum',
    'inexistir': r'\binexist(?:ir|e|en|iendo|ía)\b', 'algoidad': r'\balgoidad', 'anidentidad': r'\banidentidad',
    'unimultiplicidad': r'\bunimultiplicidad', 'repelencia': r'\brepelencia', 'hiperespecificidad': r'\bhiper-?especific',
    'irrepresentabilidad': r'\birrepresentab', 'discretivo / discretividad': r'\bdiscretiv', 'nadidad': r'\bnadidad',
    'Nadie (concepto)': r'(?<=[a-záéíóúñ,;] )Nadie\b', 'sí (sustantivo)': r'\b(?:el|del|al|su) sí\b',
}
apar = {}
for nombre, rx in TERMINOS.items():
    R = re.compile(rx)
    hits = []
    for v in V:
        n_ = len(R.findall(textos[v['obra']][v['x']:v['y']]))
        if n_:
            hits.append((v['t'], v['fecha'], v['titulo'], v['carpeta'], n_))
    por_carpeta = collections.Counter()
    for h in hits:
        por_carpeta[h[3]] += h[4]
    hits.sort()
    apar[nombre] = {'primera': {'fecha': hits[0][1], 'obra': hits[0][2]} if hits else None,
                    'antes_de_mas0': sum(h[4] for h in hits if h[3] not in ('VI - +0', 'en curso (sin carpeta)')),
                    'en_mas0': sum(h[4] for h in hits if h[3] == 'VI - +0'),
                    'primeras_obras': list(dict.fromkeys(h[2] for h in hits))[:5],
                    'por_carpeta': dict(por_carpeta)}
res['terminos'] = apar
# ventanas mínimas para el gráfico
res['puntos'] = [{'o': v['titulo'], 'c': v['carpeta'], 't': round(v['t'], 3), 'f': round(v['formal'], 3), 'l': round(v['lexica'], 3),
                  'conf': v['confianza']} for v in V]
json.dump(res, open('genealogia.json', 'w'), ensure_ascii=False, indent=1)
# las ventanas fechadas, para vectores.py
import pickle
pickle.dump([{k: v[k] for k in ('obra', 'titulo', 'carpeta', 't', 'fecha', 'confianza', 'lem', 'formal', 'lexica', 'x', 'y')} for v in V],
            open('ventanas.pkl', 'wb'))

print('pesos formales:', pesos_formal)
print('léxico +0 (top 40):', list(LEX)[:40])
for firma in ('formal', 'lexica'):
    r = res[firma]
    print(f"\n[{firma}] cruce ¼: {r['cruce_25']}  cruce ½: {r['cruce_50']}")
    print('  por carpeta:', r['por_carpeta'])
    print('  serie:', [(g, y) for g, y, _ in r['serie']][::2])
    print('  proto (%d):' % len(r['proto']), [(p['obra'], p['fecha'][:7], p['valor']) for p in r['proto'][:25]])
print('\ntérminos:')
for k, v in apar.items():
    print(f"  {k:28s} primera {v['primera']}  antes {v['antes_de_mas0']:4d}  +0 {v['en_mas0']:4d}  {v['primeras_obras']}")
print('\nnúcleos:')
for k, v in nucleos.items():
    print(' ', k, v['primera_ventana_a_nivel_mas0'], v['por_anio'])
