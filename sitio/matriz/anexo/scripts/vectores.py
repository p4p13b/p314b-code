"""Fase 5 · vectores. Los nodos cuya trayectoria converge sobre Términos y
condiciones y +0, qué los llevó hasta ahí y cómo emergieron y variaron.

Nodos convergentes: lemas que existían antes de 2023 (≥ 5 apariciones en ≥ 2
obras) y cuya densidad en Términos y condiciones Y en +0 es al menos 3 veces
la de antes (2017-2022).

Vectores textuales (portadores): para cada nodo, las obras anteriores a TyC
donde su densidad es ≥ 2 veces la suya de base. Las obras que portan más
nodos, y las cadenas entre portadores consecutivos, son los vectores.

Vector semántico (registro): en qué contexto aparece cada nodo en cada
período. Dos medidas del contexto: la firma léxica de +0 de las ventanas
donde aparece (fase 4) y la parte de su vecindario (±10) que es léxico
lírico (el núcleo de Nadie: alma, eternidad, soledad… y su emergencia). Un
nodo «migra» si su contexto pasa de lírico a teórico.

Emergencia: primera aparición, años con presencia antes de 2023,
concentración (qué parte de su uso previo está en una sola obra) y forma
(continua, en ráfaga, latente).

Lee ventanas.pkl (genealogia.py) y escribe vectores.json.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, pickle, math, collections, statistics

V = pickle.load(open('ventanas.pkl', 'rb'))
NUC = json.load(open('consenso.json'))['nucleos']
# el núcleo lírico es el que tiene eterno/eterna/eternidad (su nombre cambia con la lematización)
LIRICO = set(next((n['miembros'] for n in NUC if any(m.startswith('etern') for m in [n['palabra']] + n['miembros'])), [])) | {
    'alma', 'eternidad', 'eterno', 'soledad', 'muerte', 'vida', 'cielo', 'noche', 'luz', 'amor', 'sangre', 'dios',
    'espiritu', 'mar', 'tierra', 'fuego', 'llanto', 'dolor', 'sueño', 'silencio', 'lagrima', 'rosa', 'luna', 'sol'}


def periodo(v):
    if v['carpeta'] == 'VI - +0':
        return '+0'
    if v['obra'] == 'terminos-y-condiciones':
        return 'TyC'
    if v['t'] < 2020:
        return '2017-19'
    if v['t'] < 2023:
        return '2020-22'
    if v['carpeta'] == 'en curso (sin carpeta)':
        return None
    return '2023-25'  # Esa gran orbe, Cell, Denso, Tuyo, No, De repetir (sin TyC)


PER = ['2017-19', '2020-22', 'TyC', '2023-25', '+0']
tok = collections.Counter(); cnt = collections.defaultdict(collections.Counter)
obra_tok = collections.Counter(); obra_cnt = collections.defaultdict(collections.Counter)
por_anio = collections.defaultdict(collections.Counter)
for v in V:
    p = periodo(v)
    if not p:
        continue
    tok[p] += len(v['lem'])
    c = collections.Counter(v['lem'])
    cnt[p].update(c)
    if v['t'] < 2023:
        obra_tok[v['obra']] += len(v['lem'])
        obra_cnt[v['obra']].update(c)
        for w, n in c.items():
            por_anio[w][int(v['t'])] += n
rate = lambda w, p: cnt[p][w] / tok[p] * 1e4
antes_tok = tok['2017-19'] + tok['2020-22']

nodos = []
for w in set(cnt['TyC']) & set(cnt['+0']):
    antes = cnt['2017-19'][w] + cnt['2020-22'][w]
    obras_antes = [o for o in obra_cnt if obra_cnt[o][w]]
    if antes < 5 or len(obras_antes) < 2 or len(w) < 4:
        continue
    base = antes / antes_tok * 1e4
    rt, r0 = rate(w, 'TyC'), rate(w, '+0')
    if rt >= 3 * base and r0 >= 3 * base and cnt['TyC'][w] >= 5 and cnt['+0'][w] >= 8:
        nodos.append({'nodo': w, 'base': base, 'TyC': rt, '+0': r0, 'antes': antes,
                      'fuerza': math.log(min(rt, r0) / base) * math.log1p(cnt['TyC'][w] + cnt['+0'][w])})
nodos.sort(key=lambda x: -x['fuerza'])
nodos = nodos[:60]
print(len(nodos), 'nodos convergentes', flush=True)

# ── portadores (vectores textuales) ──
TIT = {v['obra']: v['titulo'] for v in V}
FECHA_OBRA = {}
for v in V:
    FECHA_OBRA.setdefault(v['obra'], []).append(v['t'])
FECHA_OBRA = {o: statistics.median(ts) for o, ts in FECHA_OBRA.items()}
# Aire en la cuerda y De embriaguez y pathos comparten el 91 % del texto: son
# un mismo portador (la familia se cuenta una vez por nodo).
FAMILIA = {'de-embriaguez-y-pathos': 'aire-en-la-cuerda'}
TIT['aire-en-la-cuerda'] = 'Aire en la cuerda / De embriaguez y pathos'
porta = collections.Counter(); cadenas = collections.Counter()
for n in nodos:
    w = n['nodo']
    port = [o for o in obra_cnt if obra_tok[o] > 3000 and obra_cnt[o][w] / obra_tok[o] * 1e4 >= 2 * n['base'] and obra_cnt[o][w] >= 3]
    port = list(dict.fromkeys(FAMILIA.get(o, o) for o in port))
    port.sort(key=lambda o: FECHA_OBRA[o])
    n['portadores'] = [TIT[o] for o in port]
    for o in port:
        porta[o] += 1
    seq = port + ['terminos-y-condiciones']
    for a, b in zip(seq, seq[1:]):
        cadenas[(a, b)] += 1
    # emergencia
    anios = por_anio[w]
    n['primera'] = min(anios) if anios else None
    n['anios_presente_antes'] = len([y for y in anios if y < 2023])
    tot = sum(obra_cnt[o][w] for o in obra_cnt)
    n['concentracion'] = round(max(obra_cnt[o][w] for o in obra_cnt) / tot, 2) if tot else None
    pres = n['anios_presente_antes']
    n['forma'] = 'continua' if pres >= 5 and n['concentracion'] < .4 else ('ráfaga' if n['concentracion'] >= .5 else 'latente')

# ── registro del contexto por período (vector semántico) ──
def contexto(w):
    out = {}
    for p in PER:
        lex, lir, nlir = [], 0, 0
        for v in V:
            if periodo(v) != p or w not in v['lem']:
                continue
            lem = v['lem']
            lex.append(v['lexica'])
            for i, x in enumerate(lem):
                if x == w:
                    vec = lem[max(0, i - 10): i] + lem[i + 1: i + 11]
                    lir += sum(1 for y in vec if y in LIRICO); nlir += len(vec)
        out[p] = {'lexica': round(statistics.mean(lex), 3) if lex else None, 'lirico': round(lir / nlir, 3) if nlir else None,
                  'ventanas': len(lex)}
    return out


def vecinos(w, p, k=6):
    c = collections.Counter()
    for v in V:
        if periodo(v) != p:
            continue
        lem = v['lem']
        for i, x in enumerate(lem):
            if x == w:
                c.update(y for y in lem[max(0, i - 8): i] + lem[i + 1: i + 9] if y != w and len(y) > 3)
    # los más propios de ese período (frecuencia × rareza en el período)
    return [y for y, n in sorted(c.items(), key=lambda kv: -kv[1] * math.log(1 + tok[p] / (1 + cnt[p][kv[0]])))[:k]]


# parte lírica del vecindario de una palabra cualquiera antes de 2023 (base)
_l = _t = 0
for v in V:
    if v['t'] < 2023:
        _l += sum(1 for y in v['lem'] if y in LIRICO); _t += len(v['lem'])
LIR_BASE = _l / _t
print('base lírica del cuerpo antes de 2023:', round(LIR_BASE, 3))
for n in nodos:
    w = n['nodo']
    n['contexto'] = contexto(w)
    n['vecinos'] = {p: vecinos(w, p) for p in ('2017-19', '2020-22', 'TyC', '+0')}
    temp = [n['contexto'][p]['lirico'] for p in ('2017-19', '2020-22') if n['contexto'][p]['lirico'] is not None]
    tarde = [n['contexto'][p]['lirico'] for p in ('TyC', '+0') if n['contexto'][p]['lirico'] is not None]
    lx_temp = [n['contexto'][p]['lexica'] for p in ('2017-19', '2020-22') if n['contexto'][p]['lexica'] is not None]
    n['lirico_antes'] = round(statistics.mean(temp), 3) if temp else None
    n['lirico_despues'] = round(statistics.mean(tarde), 3) if tarde else None
    n['teorico_antes'] = round(max(lx_temp), 3) if lx_temp else None
    la, ld = n['lirico_antes'], n['lirico_despues']
    if la is not None and ld is not None and la >= LIR_BASE and ld <= la / 2:
        n['tipo'] = 'migrante'   # venía en contexto lírico y lo dejó
    elif la is not None and la < LIR_BASE:
        n['tipo'] = 'residente'  # ya estaba en contexto no lírico (prosa, argumento)
    else:
        n['tipo'] = 'mixto'
    for k in ('base', 'TyC', '+0', 'fuerza'):
        n[k] = round(n[k], 2)

# ── atractores: el vecindario agregado de todos los nodos, por período ──
NODOS = {n['nodo'] for n in nodos}
atr = {}
for p in PER:
    c = collections.Counter()
    for v in V:
        if periodo(v) != p:
            continue
        lem = v['lem']
        for i, x in enumerate(lem):
            if x in NODOS:
                c.update(y for y in lem[max(0, i - 8): i] + lem[i + 1: i + 9] if y not in NODOS and len(y) > 3)
    tot_c = sum(c.values())
    # propio del período: frecuencia en el vecindario sobre su frecuencia general antes de 2023
    base_g = collections.Counter()
    for q in ('2017-19', '2020-22'):
        base_g.update(cnt[q])
    punt = {y: (k / tot_c) / ((base_g[y] + cnt[p][y] + 5) / (antes_tok + tok[p])) for y, k in c.items() if k >= 6}
    atr[p] = [y for y, _ in sorted(punt.items(), key=lambda kv: -kv[1] * math.log(1 + c[kv[0]]))[:14]]
res_atr = atr
res = {'atractores': res_atr, 'nodos': nodos,
       'portadores': [{'obra': TIT[o], 'slug': o, 'fecha': round(FECHA_OBRA[o], 2), 'nodos': k} for o, k in porta.most_common(20)],
       'cadenas': [{'de': TIT[a], 'a': TIT.get(b, 'Términos y condiciones'), 'nodos': k} for (a, b), k in cadenas.most_common(25)],
       'tipos': collections.Counter(n['tipo'] for n in nodos), 'formas': collections.Counter(n['forma'] for n in nodos),
       'lirico_base': round(LIR_BASE, 3),
       'primera_aparicion': dict(sorted(collections.Counter(n['primera'] for n in nodos).items())),
       'lirico_periodo': {p: round(statistics.mean(n['contexto'][p]['lirico'] for n in nodos if n['contexto'][p]['lirico'] is not None), 3) for p in PER}}
json.dump(res, open('vectores.json', 'w'), ensure_ascii=False, indent=1)

print('tipos:', dict(res['tipos']), ' formas:', dict(res['formas']))
print('lírico del contexto por período (media de los nodos):', res['lirico_periodo'])
print('\nportadores:', [(p['obra'], p['fecha'], p['nodos']) for p in res['portadores'][:14]])
print('\ncadenas:', [(c['de'], c['a'], c['nodos']) for c in res['cadenas'][:14]])
print('primera aparición por año:', res['primera_aparicion'])
for p in PER:
    print('  atractor', p, res_atr[p])
for w in ('absoluto', 'sujeto', 'relacion', 'positivar', 'imposible', 'valor', 'elemento', 'condicion', 'producir', 'verdadero'):
    n = next((x for x in nodos if x['nodo'] == w), None)
    if n:
        print(' ', w, {p: n['vecinos'][p] for p in n['vecinos']})
print()
for n in nodos[:40]:
    print(f"{n['nodo']:16s} base {n['base']:5.1f} TyC {n['TyC']:6.1f} +0 {n['+0']:6.1f} | 1ª {n['primera']} años {n['anios_presente_antes']} conc {n['concentracion']} {n['forma']:9s} | {n['tipo'][:12]:12s} lír {n['lirico_antes']}→{n['lirico_despues']} teo {n['teorico_antes']} | {n['portadores'][:4]}")
