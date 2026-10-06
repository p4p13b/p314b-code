#!/usr/bin/env python3
"""
teselas.py — lo que el mosaico del índice muestra de cada texto, además
del título: su peso relacional y algunas frases suyas para citar. Escribe
teselas.json. No toca ninguna fuente: las lee.

    python teselas.py

Peso relacional (primer criterio del tamaño de la tesela; las palabras
vienen después y pesan poco). Sale de acciones.json:

  · cada ancla diagonal del texto suma según su rol en el texto:
      estructural  el ancla articula: tiene dos o más pares, o alguna de
                   sus relaciones lleva emergente de la autora;
      transición   un enlace de paso: un solo par y sin emergente (una
                   propuesta de la matriz aceptada como ancla vacía).
    Si la autora marcó el rol en el ancla («rol»: «estructural» o
    «transicion» en su tipo ancla-diagonal), vale lo que marcó. Si no, el
    rol es una inferencia de estos datos, no una lectura del texto.
  · cada otro texto con el que se cruza suma uno: cuánto pesa en el
    corpus, no solo cuánto se enlaza consigo mismo.
  · una diagonal y su recíproca son una sola relación (no cuentan dos).

  La cuota es la parte de todo el peso relacional del corpus que le toca
  al texto.

Frases: oraciones cerradas del propio texto (empiezan con mayúscula o un
signo de apertura y terminan en punto, cierre de pregunta o exclamación),
de 5 a 40 palabras, con paréntesis y comillas parejos. Nunca se arman ni
se recortan: si no hay ninguna que cumpla, la tesela va sin cita. Primero
las que tocan un ancla diagonal (la autora las marcó), después las de
largo medio. En verso, la oración conserva sus cortes de línea.

Lo corre publicar.py, que además arma la versión de la web (solo los
capítulos y partes publicados, y solo relaciones entre ellos).
"""
import html as html_lib
import json
import os
import re
import sys
from util import leer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generar_obra as g

SALIDA = os.path.join(HERE, 'teselas.json')
POR_UNIDAD = 6          # frases guardadas por capítulo o parte
MIN_PAL, MAX_PAL = 5, 40
PESO_ESTRUCTURAL, PESO_TRANSICION = 1.0, 0.4
PESO_PAR_EXTRA = 0.25   # cada par más allá del primero
PESO_OBRA = 1.0         # cada otro texto con el que se cruza

ABRE = '¿¡«"“‘(—–'
FIN = re.compile(r'[.!?…]["»”’)]*$')
# Corte de oración: después de . ! ? … (y comillas de cierre), antes de
# mayúscula o de un signo de apertura.
CORTE = re.compile(r'(?<=[.!?…])(["»”’)]*)\s+(?=[¿¡«"“‘(—–]?[A-ZÁÉÍÓÚÑÜ])')


def normal(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', (s or '').lower())).strip()


# ─── texto plano ───

def texto_html(body, verso):
    """Bloques de texto de un cuerpo HTML del editor. En verso, cada línea
    se conserva; en prosa, un párrafo es un bloque."""
    t = re.sub(r'(?i)<br\s*/?>', '\n', body or '')
    t = re.sub(r'(?i)</(p|div|li|h[1-6]|blockquote)>', '\n\n', t)
    t = html_lib.unescape(re.sub(r'<[^>]+>', '', t)).replace('\xa0', ' ')
    bloques = [b.strip() for b in re.split(r'\n\s*\n', t) if b.strip()]
    if not verso:
        return [re.sub(r'\s+', ' ', b) for b in bloques]
    return ['\n'.join(re.sub(r'[ \t]+', ' ', l).strip() for l in b.split('\n') if l.strip()) for b in bloques]


def texto_paginas(paginas):
    """Bloques de las páginas de un PDF. Si las líneas son cortas (mediana
    menor a 45 caracteres) es verso y se conservan; si no, prosa: se juntan
    las líneas y se arreglan los cortes de palabra con guion."""
    lineas = [l.strip() for p in paginas for l in p.split('\n') if l.strip()]
    largos = sorted(len(l) for l in lineas)
    verso = bool(largos) and largos[len(largos) // 2] < 45
    bloques = []
    for p in paginas:
        for b in re.split(r'\n\s*\n', p):
            ls = [l.strip() for l in b.split('\n') if l.strip()]
            # un número de página suelto no es texto
            ls = [l for l in ls if not re.fullmatch(r'[\divxlcIVXLC.\s]{1,6}', l)]
            if not ls:
                continue
            if verso:
                bloques.append('\n'.join(ls))
            else:
                bloques.append(re.sub(r'(\w)-\n(\w)', r'\1\2', '\n'.join(ls)).replace('\n', ' '))
    return bloques, verso


# ─── frases ───

def oraciones(bloque):
    plano = bloque.replace('\n', '  ')  # marca de línea, para no perderla
    for o in CORTE.split(plano):
        if not o or re.fullmatch(r'["»”’)]*', o):
            continue
        yield o.replace('  ', '\n').replace(' ', '\n').strip()


def pareja(o):
    return (o.count('(') == o.count(')') and o.count('«') == o.count('»')
            and o.count('“') == o.count('”') and o.count('"') % 2 == 0
            and o.count('[') == o.count(']'))


def cerrada(o):
    if not o or not (o[0].isupper() or o[0] in ABRE):
        return False
    if o[0] in '—–-' and len(o) > 1 and not o[1:].lstrip()[:1].isupper():
        return False
    # un guion suelto al principio es viñeta de lista; una sigla con números
    # («A2-», «G1») es rótulo técnico, no frase
    if o[0] == '-' or any(c.isdigit() for c in o.split()[0]):
        return False
    if not FIN.search(o) or not pareja(o):
        return False
    pal = o.split()
    if not (MIN_PAL <= len(pal) <= MAX_PAL):
        return False
    letras = sum(c.isalpha() for c in o)
    if letras < 0.6 * len(o.replace(' ', '').replace('\n', '')):
        return False
    if re.search(r'https?:|www\.|@|©|ISBN|Atribución|Licencia|\.(pdf|docx?)\b', o, re.I):
        return False
    if sum(w.isupper() and len(w) > 2 for w in pal) > len(pal) / 2:
        return False
    return True


def frases(bloques, anclas):
    """Hasta POR_UNIDAD oraciones cerradas, las mejores primero. anclas:
    [(fragmento normalizado, de la autora?)]."""
    vistas, cands = set(), []
    for i, b in enumerate(bloques):
        for o in oraciones(b):
            if not cerrada(o):
                continue
            n = normal(o)
            if n in vistas:
                continue
            vistas.add(n)
            pal = len(o.split())
            puntos = -abs(pal - 16) / 8
            for frag, autora in anclas:
                if frag and len(frag) > 8 and (frag in n or (len(n) > 20 and n in frag)):
                    puntos += 4 + (2 if autora else 0)
                    break
            if o.endswith('.'):
                puntos += 0.5
            cands.append((puntos, i, o))
    cands.sort(key=lambda c: (-c[0], c[1]))
    elegidas = [c[2] for c in cands[:POR_UNIDAD]]
    # al menos una corta, para las teselas chicas
    if elegidas and min(len(o.split()) for o in elegidas) > 12:
        cortas = [c[2] for c in cands if len(c[2].split()) <= 12]
        if cortas:
            elegidas[-1] = cortas[0]
    return elegidas


# ─── peso relacional ───

def relaciones(registro, dentro=None):
    """Anclas con sus pares y si alguna de sus relaciones tiene emergente
    de la autora. dentro: conjunto de (obra, capítulo) que cuentan (None,
    todos); una relación con un extremo afuera no cuenta."""
    acc = registro.get('acciones') or {}
    ok = lambda a: dentro is None or ((a.get('origen') or {}).get('obra'), (a.get('origen') or {}).get('capitulo')) in dentro
    anclas = {}
    for a in acc.values():
        for t in a.get('tipos') or []:
            if t.get('tipo') != 'diagonal':
                continue
            d = acc.get(t.get('destino'))
            if not d or d.get('id') == a.get('id') or not ok(a) or not ok(d):
                continue
            autora = bool((t.get('emergente') or '').strip()) and not t.get('vacia')
            for x, y in ((a, d), (d, a)):
                info = anclas.setdefault(x['id'], {'accion': x, 'pares': set(), 'autora': False})
                info['pares'].add(y['id'])
                info['autora'] = info['autora'] or autora
    return anclas


def rol_marcado(accion):
    for t in accion.get('tipos') or []:
        if t.get('tipo') == 'ancla-diagonal' and t.get('rol') in ('estructural', 'transicion'):
            return t['rol']
    return None


def peso_ancla(info):
    pares = len(info['pares'])
    rol = rol_marcado(info['accion'])
    estructural = rol == 'estructural' if rol else (pares >= 2 or info['autora'])
    w = PESO_ESTRUCTURAL if estructural else PESO_TRANSICION
    return w * (1 + PESO_PAR_EXTRA * max(0, pares - 1)), estructural


def pesos(registro, dentro=None):
    """{obra: {'rel', 'estructurales', 'transicion', 'autora', 'obras',
    'caps': {cap: rel}}} y el total del corpus."""
    acc = registro.get('acciones') or {}
    anclas = relaciones(registro, dentro)
    salida = {}
    for aid, info in anclas.items():
        o = info['accion'].get('origen') or {}
        obra, cap = o.get('obra'), o.get('capitulo')
        if not obra:
            continue
        w, estructural = peso_ancla(info)
        r = salida.setdefault(obra, {'rel': 0.0, 'estructurales': 0, 'transicion': 0, 'autora': 0,
                                     'obras': set(), 'caps': {}, '_obras_cap': {}})
        r['rel'] += w
        r['estructurales' if estructural else 'transicion'] += 1
        r['autora'] += 1 if info['autora'] else 0
        r['caps'][cap] = r['caps'].get(cap, 0.0) + w
        otras = {(acc.get(p, {}).get('origen') or {}).get('obra') for p in info['pares']} - {obra, None}
        r['obras'] |= otras
        r['_obras_cap'].setdefault(cap, set()).update(otras)
    for r in salida.values():
        r['rel'] += PESO_OBRA * len(r['obras'])
        for cap, os_ in r['_obras_cap'].items():
            r['caps'][cap] += PESO_OBRA * len(os_)
        r['obras'] = len(r['obras'])
        del r['_obras_cap']
    total = sum(r['rel'] for r in salida.values()) or 1
    for r in salida.values():
        r['cuota'] = round(r['rel'] / total, 4)
        r['rel'] = round(r['rel'], 2)
        r['caps'] = {c: round(v, 2) for c, v in r['caps'].items()}
    return salida


# ─── armado ───

def frases_obra(slug, fuente, unidades, es_pdf, anclas_por_cap):
    caps = {}
    if es_pdf:
        paginas = g.texto_pdf(fuente)
        ultima = max(paginas or {1: ''})
        for u in unidades:
            pgs = [paginas.get(p, '') for p in range(u.get('paginaDesde') or 1, (u.get('paginaHasta') or ultima) + 1)]
            bloques, _ = texto_paginas(pgs)
            fs = frases(bloques, anclas_por_cap.get(u.get('id'), []))
            if fs:
                caps[u['id']] = fs
    else:
        for u in unidades:
            fs = frases(texto_html(u.get('body'), bool(u.get('poesia'))), anclas_por_cap.get(u.get('id'), []))
            if fs:
                caps[u['id']] = fs
    return caps


def armar(obras, registro, dentro=None):
    """obras: [(slug, fuente, es_pdf, unidades)]."""
    rel = pesos(registro, dentro)
    anclas = relaciones(registro, dentro)
    por_cap = {}
    for info in anclas.values():
        o = info['accion'].get('origen') or {}
        por_cap.setdefault(o.get('obra'), {}).setdefault(o.get('capitulo'), []).append(
            (normal(o.get('fragmento')), info['autora']))
    salida = {}
    for slug, fuente, es_pdf, unidades in obras:
        t = {'frases': frases_obra(slug, fuente, unidades, es_pdf, por_cap.get(slug, {}))}
        if slug in rel:
            t.update(rel[slug])
        salida[slug] = t
    return {'obras': salida}


def todas():
    out = []
    for ruta in sorted(os.listdir(os.path.join(HERE, 'obras'))):
        if not ruta.endswith('.json') or ruta.endswith('-citas.json'):
            continue
        fuente = leer(os.path.join(HERE, 'obras', ruta), None)
        if not isinstance(fuente, dict) or not fuente.get('book'):
            continue
        es_pdf = fuente.get('tipo') == 'pdf'
        unidades = g.normalizar_partes(fuente.get('partes') or []) if es_pdf else g.normalizar_capitulos(fuente.get('chapters') or [])
        out.append((ruta[:-5], fuente, es_pdf, unidades))
    return out


def escribir(salida=SALIDA):
    datos = armar(todas(), leer(os.path.join(HERE, 'acciones.json'), {'acciones': {}}))
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    return datos


if __name__ == '__main__':
    d = escribir()
    n = sum(1 for t in d['obras'].values() if t['frases'])
    print(f'teselas.json: {len(d["obras"])} textos, {n} con frases')
