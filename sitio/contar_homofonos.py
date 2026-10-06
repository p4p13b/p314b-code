#!/usr/bin/env python3
"""
contar_homofonos.py — cuántas veces aparece cada homófono en tus textos,
para elegir a ojo qué grupos van en homofonos.json (la lista que el taller
recorre en el panel "homofonías", donde marcás una por una las apariciones
que cambian al leer).

    python contar_homofonos.py            # candidatos (lista de abajo)
    python contar_homofonos.py --lista    # solo los grupos de homofonos.json

Cuenta en los posteos de sitio/obras (donde corre el efecto) y, aparte, en
el corpus de LeE (datos-lee/txt), solo como referencia.
"""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# Homófonos en castellano rioplatense: h muda, b/v, seseo (s/c/z), yeísmo (ll/y).
CANDIDATOS = [
    ['voz', 'vos'], ['hecho', 'echo'], ['siento', 'ciento'], ['hay', 'ay'], ['haya', 'halla', 'aya'],
    ['casa', 'caza'], ['casar', 'cazar'], ['coser', 'cocer'], ['ola', 'hola'], ['abría', 'habría'],
    ['tubo', 'tuvo'], ['vello', 'bello'], ['votar', 'botar'], ['hierba', 'hierva'], ['ves', 'vez'],
    ['has', 'haz', 'as'], ['sabia', 'savia'], ['rallar', 'rayar'], ['valla', 'vaya', 'baya'],
    ['cayó', 'calló'], ['asta', 'hasta'], ['errar', 'herrar'], ['onda', 'honda'], ['uso', 'huso'],
    ['bienes', 'vienes'], ['basta', 'vasta'], ['ciervo', 'siervo'], ['cien', 'sien'], ['cima', 'sima'],
    ['rosa', 'roza'], ['abrazar', 'abrasar'], ['cause', 'cauce'], ['sesión', 'cesión'],
    ['ciega', 'siega'], ['consejo', 'concejo'], ['hora', 'ora'], ['hojear', 'ojear'], ['grabe', 'grave'],
    ['desecho', 'deshecho'], ['revelar', 'rebelar'], ['tasa', 'taza'], ['losa', 'loza'], ['pollo', 'poyo'],
    ['olla', 'hoya'], ['arrollo', 'arroyo'], ['callado', 'cayado'], ['vaso', 'bazo'], ['sumo', 'zumo'],
    ['echa', 'hecha'], ['echar', 'hechar'], ['hice', 'ice'], ['hizo', 'izo'], ['ay', 'hay', 'ahí'],
    ['sé', 'se'], ['vote', 'bote'], ['bacilo', 'vacilo'], ['nobel', 'novel'], ['ceso', 'seso'],
    ['cera', 'sera'], ['cierra', 'sierra'], ['caso', 'cazo'], ['maza', 'masa'], ['poso', 'pozo'],
    ['ase', 'hace'], ['hacía', 'asía'], ['hablando', 'ablando'], ['hecho', 'echo'],
]


def palabras(texto):
    return re.findall(r'[a-záéíóúüñ]+', texto.lower())


def posteos():
    for ruta in sorted(glob.glob(os.path.join(HERE, 'obras', '*.json'))):
        if ruta.endswith('-citas.json'):
            continue
        try:
            with open(ruta, encoding='utf-8') as f:
                o = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        cuerpo = ' '.join(re.sub(r'<[^>]+>', ' ', c.get('body') or '') for c in o.get('chapters') or [])
        if cuerpo.strip():
            yield os.path.splitext(os.path.basename(ruta))[0], cuerpo


def main():
    grupos = CANDIDATOS
    if '--lista' in sys.argv:
        with open(os.path.join(HERE, 'homofonos.json'), encoding='utf-8') as f:
            grupos = json.load(f).get('grupos', [])
    vistos, unicos = set(), []
    for g in grupos:
        k = tuple(sorted(g))
        if k not in vistos:
            vistos.add(k)
            unicos.append(g)
    en_post, donde = Counter(), defaultdict(Counter)
    for slug, texto in posteos():
        for w in palabras(texto):
            en_post[w] += 1
            donde[w][slug] += 1
    en_lee = Counter()
    for ruta in glob.glob(os.path.join(HERE, '..', 'datos-lee', 'txt', '*-txt', '*.txt')):
        with open(ruta, encoding='utf-8', errors='replace') as f:
            en_lee.update(palabras(f.read()))
    filas = []
    for g in unicos:
        n = sum(en_post[w] for w in g)
        filas.append((n, g))
    print('posteos del sitio (donde corre el efecto) · entre paréntesis, en LeE\n')
    for n, g in sorted(filas, key=lambda x: -x[0]):
        if not n and not any(en_lee[w] for w in g):
            continue
        partes = ' / '.join(f'{w} {en_post[w]} ({en_lee[w]})' for w in g)
        obras = Counter()
        for w in g:
            obras.update(donde[w])
        top = ', '.join(f'{s} {c}' for s, c in obras.most_common(4))
        print(f'{n:5}  {partes}' + (f'   ← {top}' if top else ''))


if __name__ == '__main__':
    main()
