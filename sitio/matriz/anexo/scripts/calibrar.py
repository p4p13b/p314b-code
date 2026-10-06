"""Calibración del protocolo de no teoría (C.2) sobre el texto que C.2 mide
(C.1, pp. 5–10), IIN por sección de no teoría y correlaciones con la
matriz. Lee criterios.json (de criterios.py) y escribe calibracion.json."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, statistics
import criterios_base as cb

raw = open(RAIZ + 'datos-lee/txt/VI-0-txt/I- no teoría.txt', encoding='utf-8').read()
partes = re.split(r'<<<PAGE (\d+)>>>', raw)
PAG = {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)}


def paginas(a, b):
    return '\n'.join(PAG[i] for i in range(a, b + 1) if i in PAG)


# Valores que no teoría declara para su propio texto (C.2, pp. 14–29).
AUTORA = {'T': 2453, 'V': 883, 'TTR': 0.36, 'Vinst': 1780, 'TTRinst': 0.72, 'Vg': 25, 'Eg': 0.014,
          'Vf': 27, 'Ef': 0.011, 'Vc': 68, 'Esint': 0.028, 'DRI': 0.02, 'IIN': 10.64}
c1 = cb.medir_ventana(paginas(5, 10).replace('C.1', ''), detalle=True)

SECCIONES = [('C.1 · poema', 5, 10), ('C.2 · protocolo', 11, 30), ('C.3 · mundos', 31, 51), ('C.4 + boceto', 52, 60),
             ('ci:TA', 61, 70), ('ci:C', 71, 75), ('ci:Q … ci:N', 76, 84), ('S1–S2', 85, 97)]
secciones = []
for nombre, a, b in SECCIONES:
    m = cb.medir_ventana(paginas(a, b))
    if m:
        secciones.append({'seccion': nombre, 'paginas': [a, b], **{k: round(v, 4) for k, v in m.items()}})

R = json.load(open('criterios.json'))
es = {s: r for s, r in R.items() if r['idioma'] == 'es'}


def rangos(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0] * len(x)
    for k, i in enumerate(o):
        r[i] = k
    return r


def spearman(a, b):
    ra, rb = rangos(a), rangos(b); n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


S = list(es)
densidad = [es[s]['propuestas'] / max(1, es[s]['pasajes']) for s in S]
correl = {k: round(spearman([es[s][k] for s in S], densidad), 2) for k in ('costo', 'hiper', 'IIN', 'cq', 'Esint', 'Eg', 'DRI', 'dos', 'TTR')}
ULTIMAS = cb.ULTIMAS
comparacion = {}
for k in ('IIN', 'TTR', 'TTRinst', 'Eg', 'Ef', 'Esint', 'DRI', 'cq', 'costo', 'hiper', 'dos'):
    a = [es[s][k] for s in es if s in ULTIMAS]; b = [es[s][k] for s in es if s not in ULTIMAS]
    comparacion[k] = {'ultimas': round(statistics.mean(a), 4), 'resto': round(statistics.mean(b), 4)}
# Cronología (fechas.py → fechas.json): tendencia de cada criterio en el
# tiempo (ρ con el orden cronológico) y promedio por carpeta.
FECHAS = json.load(open('fechas.json'))
fechadas = [s for s in es if FECHAS.get(s, {}).get('orden')]
tendencia = {k: round(spearman([es[s][k] for s in fechadas], [FECHAS[s]['orden'] for s in fechadas]), 2)
             for k in ('IIN', 'TTR', 'Eg', 'Ef', 'Esint', 'DRI', 'cq', 'costo', 'hiper', 'dos')}
por_carpeta = {}
for s in fechadas:
    por_carpeta.setdefault(FECHAS[s]['carpeta'], []).append(s)
por_carpeta = {c: {'obras': len(v), **{k: round(statistics.mean(es[s][k] for s in v), 4) for k in ('IIN', 'cq', 'costo', 'hiper', 'dos', 'Esint', 'Eg')}}
               for c, v in sorted(por_carpeta.items(), key=lambda x: x[0].split(' ')[0].replace('VI', '6').replace('IV', '4').replace('V', '5').replace('III', '3').replace('II', '2').replace('I', '1'))}
ventana_min = min(((r['IIN_min'], r['titulo']) for r in es.values()))
json.dump({'autora': AUTORA, 'c1': c1, 'secciones_no_teoria': secciones, 'spearman_con_propuestas_por_pasaje': correl,
           'ultimas_vs_resto': comparacion, 'ventana_minima': {'IIN': ventana_min[0], 'obra': ventana_min[1]},
           'tendencia_cronologica': tendencia, 'por_carpeta': por_carpeta, 'ultimas': sorted(ULTIMAS)},
          open('calibracion.json', 'w'), ensure_ascii=False, indent=1)
print('C.1:', {k: round(v, 4) if isinstance(v, float) else v for k, v in c1.items()})
print('ρ con propuestas/pasaje:', correl)
print('últimas vs resto:', comparacion)
print('tendencia en el tiempo:', tendencia)
for k, v in por_carpeta.items():
    print(' ', k, v)
