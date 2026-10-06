"""Junta los resultados del anexo en sitio/matriz/anexo/datos/, que es lo
único que lee matriz-anexo.html. La página no calcula nada: muestra estos
archivos tal cual.

  fase1-semillas.json    las diagonales de la autora y los significantes
                         (con sus familias lemáticas) que se tomaron de ellas
  fase2-nucleos.json     la expansión: núcleos estables, su palabra, la
                         acuñación que emerge, obras en diagonal y testigos
  fase3-criterios.json   la sobredeterminación: los cinco criterios de las
                         últimas obras aplicados a cada obra, con la calibración
  fase4-gestacion.json   la gestación: desde dónde se fue armando +0
  fase5-vectores.json    los vectores: qué portó los nodos convergentes y cómo
                         se desplazó su contexto
  fase6-emergencia.json  sin semillas: conceptos, operadores, diagonales e
                         instrumentos que salen de la estructura del cuerpo
  fase7-categorias.json  las propuestas de la matriz reducidas a tipos de
                         relación que sostiene el material, el examen de los
                         instrumentos de la autora, herramientas y conceptos
"""
from _rutas import RAIZ, DATOS  # rutas y carpeta de trabajo
import json, os, re, sys, collections
import numpy as np
from lematica import norm
from estructural_semillas import SEMILLAS

sys.path.insert(0, os.path.join(RAIZ, 'sitio', 'matriz'))
import comun  # noqa: E402

P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
META = P['meta']['sitios']
from claves import meta_por_clave
META_CLAVE = meta_por_clave(P)  # para lo agrupado por obra_clave
EST = json.load(open('estructural.json'))
CONS = json.load(open('consenso.json'))
NUC = json.load(open('nucleos_lematicos.json'))
CRIT = json.load(open('criterios.json'))
CAL = json.load(open('calibracion.json'))
DUP = json.load(open('duplicados.json'))


def extracto(t, palabras, largo=340):
    """Recorte del pasaje centrado en la primera palabra del núcleo."""
    t = re.sub(r'\s+', ' ', t or '').strip()
    pos = [m.start() for w in palabras for m in re.finditer(r'\b' + re.escape(w), t, re.I)]
    if not pos:
        return recortar(t)
    a = max(0, min(pos) - 110)
    s = t[a:a + largo]
    if a > 0:
        s = '…' + s[s.find(' ') + 1:]
    if a + largo < len(t):
        s = s[:s.rfind(' ')] + '…'
    return s


def recortar(t, n=320):
    t = re.sub(r'\s+', ' ', t or '').strip()
    return t if len(t) <= n else t[:n].rsplit(' ', 1)[0] + '…'


# ── Fase 1 ──
# De qué diagonal sale cada significante semilla (instrumento, título o los
# lemas que la autora marcó en la diagonal).
ORIGEN = {
    'Nadie': ['nadie', 'nadie-realizado'],
    'mismidad': ['mismidad-y-devenir', 'indiferir-como-mismizacion-instrumental'],
    'indiferir': ['indiferir-como-mismizacion-instrumental', 'indiferibilidad'],
    'discernir': ['indiferibilidad'],
    'identidad': ['indiferibilidad'],
    'objetivar': ['indiferibilidad'],
    'instrumental': ['indiferir-como-mismizacion-instrumental'],
    'devenir': ['mismidad-y-devenir'],
    'el sí': ['indiferibilidad'],
    'Rimbaud': ['rimbaud'],
}
diagonales = []
for d in comun.diagonales_confirmadas():
    t = d.get('tipo') or {}
    diagonales.append({'id': d['id'], 'obra': (d.get('origen') or {}).get('obra'),
                       'instrumento': t.get('instrumento'), 'titulo': t.get('titulo') or t.get('instrumento_nuevo_label'),
                       'lemas': t.get('lemas') or [], 'tipo_relacion': t.get('tipo_relacion'),
                       'fragmento': recortar((d.get('origen') or {}).get('fragmento'), 200)})
semillas = []
for nombre, fam in SEMILLAS.items():
    s = EST['salida'].get(nombre, {})
    semillas.append({'semilla': nombre, 'familia': sorted(fam), 'diagonales': ORIGEN.get(nombre, []),
                     'ocurrencias': s.get('n'), 'obras': s.get('obras'),
                     'obras_top': [[META_CLAVE[o]['titulo'], n] for o, n in s.get('obras_top', [])]})
fase1 = {'descripcion': 'Significantes tomados de las diagonales de la autora y sus variaciones lemáticas.',
         'diagonales': diagonales, 'semillas': semillas}

# ── Fase 2 ──
# La acuñación de cada núcleo: palabra rara que el núcleo concentra en obras
# de series distintas, elegida por cercanía al centro del núcleo (E.npy).
ACUNADA = {'diferir': 'inexistir', 'existencia': 'algoidad', 'realizacion': 'anidentidad', 'experienc': 'anidentidad',
           'continuo': 'indiferenciacion', 'imposibilidad': 'irrepresentabilidad', 'eterno': 'nadidad', 'modalidad': 'modaliz'}
VOC = EST['voc']; ID = {c: i for i, c in enumerate(VOC)}
E = np.load('E.npy')
obras_de = EST['obras_de']
corpus = __import__('pickle').load(open('corpus.pkl', 'rb'))
frec_obra = collections.defaultdict(collections.Counter)
for x in corpus['docs']:
    for c in x['claves']:
        frec_obra['sí' if c == 'sí' else norm(c)][x['obra']] += 1
nucleos = []
for n, info in zip(CONS['nucleos'], NUC):
    m = [ID[c] for c in n['miembros'] if c in ID]
    cen = E[m].mean(0); cen /= np.linalg.norm(cen)
    ac = ACUNADA.get(n['palabra'])
    sim = round(float(E[ID[ac]] @ cen), 2) if ac in ID else None
    fo = frec_obra.get(ac) or collections.Counter()
    nucleos.append({
        'palabra': info['palabra'], 'clave': n['palabra'], 'miembros': info['miembros'],
        'consenso': n['consenso'], 'cohesion': n['cohesion'], 'semillas': info['semillas'],
        'acunada': {'palabra': (corpus['formas_de'].get(ac) or collections.Counter({ac: 1})).most_common(1)[0][0], 'clave': ac, 'cercania_al_centro': sim, 'ocurrencias': sum(fo.values()),
                    'obras': [[META_CLAVE[o]['titulo'], k] for o, k in fo.most_common(8)]},
        'emergentes': info['emergentes'], 'ancla': info['casa'],
        'diagonal': info['diagonal'],
        'testigos': [{'obra': t['obra'], 'pagina': t.get('pagina'), 'diagonal': t['diagonal'], 'miembros': t['miembros'],
                      'texto': extracto(t.get('texto'), t['miembros'])} for t in info['testigos'][:4]],
    })
fase2 = {'descripcion': 'Expansión estructural sobre los nodos aledaños: núcleos estables por consenso '
                        '(mitades disjuntas × resoluciones × semillas de Louvain).',
         'repetidos_fuera': len(DUP), 'nucleos': nucleos}

# ── Fase 3 ──
FECHAS = json.load(open('fechas.json'))
obras = []
for s, r in CRIT.items():
    obras.append({'slug': s, 'titulo': r['titulo'], 'serie': r['serie'], 'ultima': s in __import__('criterios_base').ULTIMAS,
                  'idioma': r['idioma'], 'ventanas': r['ventanas'], 'tokens': r['tokens'],
                  **{k: r[k] for k in ('IIN', 'IIN_min', 'IIN_max', 'TTR', 'TTRinst', 'Eg', 'Ef', 'Esint', 'DRI', 'cq', 'huecos',
                                       'costo', 'hiper', 'hiper_tipos', 'plural', 'singular', 'dos', 'P_plural', 'propuestas', 'pasajes')},
                  'fecha': {k: FECHAS.get(s, {}).get(k) for k in ('carpeta', 'numero', 'desde', 'hasta', 'punto', 'fuente', 'confianza', 'notas', 'orden', 'en_curso', 'sin_fecha')}})
fase3 = {'descripcion': 'Sobredeterminación del cuerpo con el instrumental que el propio cuerpo concibe: '
                        'cinco criterios de las últimas obras (VI - +0) aplicados a cada obra, ordenadas '
                        'por la cronología de la autora (CRONOLOGIA.md).',
         'calibracion': CAL, 'obras': obras}

# ── Fase 4 ──
GEN = json.load(open('genealogia.json'))
fase4 = {'descripcion': 'Gestación: dónde empieza el cuerpo a moverse hacia +0. Ventanas fechadas dentro de cada obra; '
                        'dos firmas de +0 (formal y léxica) en un eje de 0 (I - Estudio, blogs 2017-2019) a 1 (VI - +0).',
         'ventanas': GEN['ventanas'], 'pesos_formal': GEN['pesos_formal'], 'lexico_mas0': GEN['lexico_mas0'][:60],
         'terminos': GEN['terminos'], 'nucleos': GEN['nucleos'], 'puntos': GEN['puntos']}
for firma in ('formal', 'lexica'):
    g = GEN[firma]
    fase4[firma] = {'serie': g['serie'], 'cruce_25': g['cruce_25'], 'cruce_50': g['cruce_50'], 'por_carpeta': g['por_carpeta'],
                    'proto': [dict(p, texto=recortar(p['texto'], 360)) for p in g['proto']]}

# ── Fase 5 ──
VEC = json.load(open('vectores.json'))
FORMAS = collections.defaultdict(collections.Counter)
for c_, f_ in corpus['formas_de'].items():
    FORMAS['sí' if c_ == 'sí' else norm(c_)].update(f_)
sup = lambda c_: FORMAS[c_].most_common(1)[0][0] if FORMAS.get(c_) else c_
# fuera las mitades de palabras cortadas por guion al final de línea en los PDF
# («re-/lación», «va-/riedad»): aparecen casi solo después de «-\n»
import criterios_base as _cb
_textos = '\n'.join((_cb.texto_post(m_['fuente']) if m_.get('fuente', '').endswith('.json') else _cb.texto_pdf(m_['fuente']))
                     for m_ in META.values() if m_.get('fuente'))


_textos = norm(_textos)  # sin tildes ni mayúsculas, para comparar formas
_VOCAB = set(re.findall(r"[^\W\d_]+", _textos))


def _fragmento(w):
    """La mayoría de sus apariciones son la segunda mitad de una palabra
    cortada al final de la línea (con o sin guion): pegada al final de la
    línea anterior forma una palabra que existe en el cuerpo."""
    w = norm(w)
    ocurr = list(re.finditer(r'(\w+)[-\u00ad]?\s*\n\s*(' + re.escape(w) + r')\b', _textos))
    tot_ = len(re.findall(r'\b' + re.escape(w) + r'\b', _textos))
    cort = sum(1 for m_ in ocurr if (m_.group(1) + m_.group(2)).lower() in _VOCAB)
    return tot_ and cort / tot_ > .5


VEC['atractores'] = {p: [sup(w) for w in ws if not _fragmento(sup(w))] for p, ws in VEC['atractores'].items()}
for n_ in VEC['nodos']:
    n_['clave'] = n_['nodo']; n_['nodo'] = sup(n_['nodo'])
    n_['vecinos'] = {p: [sup(w) for w in ws] for p, ws in n_['vecinos'].items()}
fase5 = {'descripcion': 'Vectores: los nodos cuya trayectoria converge sobre Términos y condiciones y +0, las obras que los '
                        'portaron, el desplazamiento de su contexto (atractores por período) y cómo emergieron.',
         'atractores': VEC['atractores'], 'portadores': VEC['portadores'], 'cadenas': VEC['cadenas'],
         'tipos': VEC['tipos'], 'formas': VEC['formas'], 'lirico_base': VEC['lirico_base'], 'lirico_periodo': VEC['lirico_periodo'],
         'primera_aparicion': VEC['primera_aparicion'],
         'nodos': [{k: n[k] for k in ('nodo', 'clave', 'base', 'TyC', '+0', 'antes', 'primera', 'anios_presente_antes', 'concentracion',
                                     'forma', 'tipo', 'lirico_antes', 'lirico_despues', 'portadores', 'vecinos')} for n in VEC['nodos']]}

# ── Fase 6 ──
EM = json.load(open('emergencia.json'))
TIT = {o: m['titulo'] for o, m in META.items()}
conceptos6 = [{'concepto': sup(f['clave']), 'clave': f['clave'], 'registro': f['registro'], 'familia': [sup(x) for x in f['familia']][:8],
               'obras': f['obras'], 'n': f['n'], 'estabilidad': round(f['estabilidad'], 3), 'operado': round(f['operado'], 2),
               'nombrado': round(f['argumento'], 2), 'ya_nombrado': f['ya_nombrado']} for f in EM['conceptos']]
operadores6 = [{k: o[k] for k in ('canon', 'tipo', 'registro', 'n', 'obras', 'lift')} for o in EM['operadores']]
instr6 = [{'concepto': sup(i['concepto']), 'operador': i['operador'], 'registro': i['registro'], 'n': i['n'],
           'obras': [TIT.get(o, o) for o in i['obras']], 'atadura': i['atadura'], 'ya_nombrado': i.get('ya_nombrado', False),
           'ejemplos': [dict(e, obra=TIT.get(e['obra'], e['obra'])) for e in i['ejemplos']]} for i in EM['instrumentos']]
diag6 = []
for d in EM['diagonales']:
    lado = lambda x: {'obra': TIT.get(x['obra'], x['obra']), 'anio': round(x['anio'], 2) if x['anio'] else None,
                      'claves': [sup(c) for c in x['claves']], 'texto': recortar(x['texto'], 360)}
    diag6.append({'a': lado(d['a']), 'b': lado(d['b']), 'estructural': d['estructural'], 'lexico': d['lexico'],
                  'eje': [sup(c) for c in d['eje']], 'alcance': d['alcance'], 'distancia': d['distancia']})
fase6 = {'descripcion': 'Emergencia sin semillas: conceptos, operadores, diagonales e instrumentos por correspondencia estructural. '
                        'Ninguna lista de la autora entra en el cálculo; se cruzan al final solo para marcar coincidencias.',
         'pasajes': EM['pasajes'], 'conceptos': conceptos6, 'operadores': operadores6, 'instrumentos': instr6, 'diagonales': diag6}

# ── Fase 7 ──
CA = json.load(open('categorias.json'))
fase7 = {'descripcion': 'Las propuestas de la matriz reducidas a tipos de relación que sostiene el propio material '
                        '(cada señal comparada con pares de pasajes al azar del cuerpo), el examen de los instrumentos de la '
                        'autora, las herramientas (procedimientos de escritura) y los conceptos.',
         'propuestas': CA['propuestas'], 'ubicadas': CA['ubicadas'], 'senales': CA['senales'], 'base': CA['base'],
         'tipos': [dict(t, conceptos=[sup(c) for c in t['conceptos']], palabras_raras=[sup(c) for c in t['palabras_raras']],
                        casos=[dict(c, a=dict(c['a'], obra=TIT.get(c['a']['obra'], c['a']['obra'])), b=dict(c['b'], obra=TIT.get(c['b']['obra'], c['b']['obra'])))
                               for c in t['casos']]) for t in CA['tipos']],
         'asignacion': {k: {'tipo': v['tipo'], 'alcance': v['alcance'], 'fuerza': v['fuerza'], 'senales': v['senales']} for k, v in CA['asignacion'].items()},
         'instrumentos': CA['instrumentos'], 'base_azar': CA['base_azar'], 'decisiones': CA['decisiones'],
         'herramientas': [dict(h, obras_top=[TIT.get(o, o) for o in h['obras_top']], ejemplos=[dict(e, obra=TIT.get(e['obra'], e['obra'])) for e in h['ejemplos']])
                          for h in CA['herramientas']],
         'conceptos': [{'concepto': c['concepto'], 'registro': c['registro'], 'obras': c['obras'], 'n': c['n'], 'operado': c['operado'],
                        'estabilidad': c['estabilidad'], 'ya_nombrado': c['ya_nombrado'], 'familia': c['familia']} for c in conceptos6[:40]],
         'nucleos': [{'nucleo': n['palabra'], 'acunada': (n.get('acunada') or {}).get('palabra'), 'consenso': n['consenso'],
                      'miembros': n['miembros'][:10]} for n in nucleos],
         'diagonales': [d for d in diag6 if d['alcance'] == 'largo'][:15]}

# ── Fase 8 ── (cutup.py ya deja escrito su json; acá se repite por si se corre todo)
fase8 = None
if os.path.exists('cutup.json'):
    import cutup_desc
    fase8 = dict(json.load(open('cutup.json')), descripcion=cutup_desc.DESCRIPCION)

os.makedirs(DATOS, exist_ok=True)
for nombre, data in (('fase1-semillas.json', fase1), ('fase2-nucleos.json', fase2), ('fase3-criterios.json', fase3),
                     ('fase4-gestacion.json', fase4), ('fase5-vectores.json', fase5), ('fase6-emergencia.json', fase6), ('fase7-categorias.json', fase7),
                     ('fase8-cutup.json', fase8)):
    if data is None:
        continue
    with open(os.path.join(DATOS, nombre), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('escrito', nombre)
