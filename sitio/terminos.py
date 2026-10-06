#!/usr/bin/env python3
"""
terminos.py — junta los términos que el lector puede resaltar al leer
(opción «resaltar términos» del panel de lectura de cada obra) y escribe
terminos.json. No toca ninguna fuente: las lee.

    python terminos.py

Cuatro categorías, cada una de lo que declaró la autora:

  glosario      nombres de las entradas del aparato conceptual (§2) del
                GLOSARIO GENERAL de datos-lee/cowork, con sus variantes
                («indiferir / indiferencia»). Sin lo que la corrección del
                autor (16/09) atribuye a Cló: epsilon, coagulación, G1-G5,
                Ax.1-Ax.7/K1-K3, +0F.
  nodos         los nodos (lemas) de sus diagonales: acciones.json y lo que
                agregó desde la visualización (diagonales.json).
  instrumentos  etiqueta y lema de cada instrumento declarado por ella
                (matriz/instrumentos.json, estatuto «autor»).
  lemas         los lemas que ella diferenció: sus reglas (mismo, mismidad,
                mismización, mismizar, mismidad-misma; indiferir,
                indiferencia) y los pares verbo / sustantivo en -encia que
                su regla mantiene separados (inexistir / inexistencia,
                existir / existencia…), con todas sus formas.

Lo corren generar_obra.py y publicar.py; también se puede correr a mano.
"""
import json
import os
import re
import unicodedata
from collections import defaultdict
from util import leer

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(HERE)
SALIDA = os.path.join(HERE, 'terminos.json')
GLOSARIO = os.path.join(RAIZ, 'datos-lee', 'cowork', 'GLOSARIO GENERAL.md')

CLO = {'epsilon', 'coagulacion', 'g1-g5', 'ax.1-ax.7', 'k1-k3', '+0f'}
REGLAS = ['mismo', 'mismidad', 'mismización', 'mismizar', 'mismidad-misma', 'indiferir', 'indiferencia']


def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def de_clo(v):
    v = sin_tildes(v.lower())
    return v in CLO or any(v.startswith(c[:6]) for c in CLO if len(c) >= 6)


def glosario():
    """Nombres (en negrita) de las entradas de §2, partidos por «/»."""
    try:
        with open(GLOSARIO, encoding='utf-8') as f:
            texto = f.read()
    except OSError:
        return []
    m = re.search(r'^## 2\..*?$(.*?)^## 3\.', texto, re.S | re.M)
    if not m:
        return []
    out = []
    for nombre in re.findall(r'^\*\*(.{2,120}?)\*\*', m.group(1), re.M):
        mayus = 'mayúscula' in nombre
        limpio = re.sub(r'\([^)]*\)', '', nombre)
        for v in re.split(r'\s*/\s*', limpio):
            v = v.strip().strip('"“”').strip()
            if len(v) < 3 or de_clo(v) or not re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]', v):
                continue
            out.append({'t': v, 'e': re.sub(r'\s+', ' ', limpio).strip(), 'exacto': mayus and v[:1].isupper()})
    return out


def nodos():
    reg = leer(os.path.join(HERE, 'acciones.json'), {}).get('acciones', {})
    dg = leer(os.path.join(HERE, 'diagonales.json'), {})
    vistos = set()
    for a in reg.values():
        for t in a.get('tipos') or []:
            if t.get('tipo') == 'diagonal':
                vistos.update(x.strip() for x in t.get('lemas') or [] if x and x.strip())
    for r in (dg.get('diagonales') or {}).values():
        vistos.update(x.strip() for x in r.get('nodos') or [] if x and x.strip())
    return [{'t': x, 'e': 'nodo de una diagonal'} for x in sorted(vistos)]


def instrumentos():
    d = leer(os.path.join(HERE, 'matriz', 'instrumentos.json'), {})
    out = []
    for i in d.get('instrumentos') or []:
        if (i.get('estatuto') or 'autor') != 'autor':
            continue
        nombre = i.get('etiqueta') or i.get('id')
        for v in [i.get('etiqueta'), *re.split(r'\s*/\s*', i.get('lema') or '')]:
            if v and len(v.strip()) >= 3:
                out.append({'t': v.strip(), 'e': 'instrumento: ' + nombre + (' › ' + i['lema'] if i.get('lema') and v.strip() != nombre else '')})
    return out


def lemas():
    d = leer(os.path.join(HERE, 'lemas.json'), {})
    formas = d.get('formas') or {}
    por_lema = defaultdict(set)
    for f, l in formas.items():
        por_lema[l].add(f)
    elegidos = set(REGLAS)
    # su regla de indiferir / indiferencia: el verbo y el sustantivo en
    # -encia de una misma raíz son lemas distintos
    todos = set(por_lema) | set(formas)
    for l in list(todos):
        m = re.match(r'^(.{3,})(encia|ancia)$', l)
        if not m:
            continue
        raiz = m.group(1)
        verbos = [raiz + t for t in ('ir', 'er', 'ar') if raiz + t in todos]
        if verbos:
            elegidos.add(l)
            elegidos.update(verbos)
    out = {}
    for l in elegidos:
        for f in por_lema.get(l, set()) | {l}:
            out[f] = l
    return [{'t': f, 'e': 'lema: ' + l} for f, l in sorted(out.items())]


def construir():
    return {
        'nota': 'Calculado por terminos.py (no se edita a mano): lo lee la opción «resaltar términos» de la lectura.',
        'glosario': glosario(),
        'nodos': nodos(),
        'instrumentos': instrumentos(),
        'lemas': lemas(),
    }


def escribir(ruta=SALIDA):
    datos = construir()
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    return datos


if __name__ == '__main__':
    d = escribir()
    print('✓ terminos.json — ' + ', '.join(f'{len(d[k])} {k}' for k in ('glosario', 'nodos', 'instrumentos', 'lemas')))
