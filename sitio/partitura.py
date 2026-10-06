"""partitura.py — rareza de cada palabra en todo el corpus (lo corre
publicar.py después de armar web/; también se puede correr a mano).

Lo leen dos opciones de lectura (lectura-extra.js):
  · partitura: cada palabra suena más aguda cuanto más rara es en el corpus;
  · sismógrafo: la densidad de palabras raras y de términos por párrafo.

Cuenta las palabras de lo escrito en la plataforma (obras/*.json) y de las
transcripciones de los PDF (Archivo/*.txt). Escribe partitura.json:
  { "n": palabras contadas, "bandas": 12,
    "b": { palabra: banda } }   0 = de las más usadas … 11 = de las más raras
Solo van las palabras que ya están en línea (web/obras/). Las que no están
en «b» (aparecen menos de MIN veces) son hápax o casi: la lectura las trata como banda 12 (lo más agudo).

    python3 partitura.py
"""
import collections
import glob
import html
import json
import math
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
TOKEN = re.compile(r'[^\W\d_]+(?:-[^\W\d_]+)*', re.U)
BANDAS = 12
MIN = 3


def texto_obra(ruta):
    try:
        d = json.load(open(ruta, encoding='utf-8'))
    except Exception:
        return ''
    caps = d.get('chapters') or []
    partes = []
    for c in caps:
        b = c.get('body') or ''
        partes.append(html.unescape(re.sub(r'<[^>]+>', ' ', b)))
    return '\n'.join(partes)


def main():
    cuenta = collections.Counter()
    for f in sorted(glob.glob(os.path.join(AQUI, 'obras', '*.json'))):
        if f.endswith('-citas.json'):
            continue
        cuenta.update(w.lower() for w in TOKEN.findall(texto_obra(f)))
    for f in sorted(glob.glob(os.path.join(AQUI, 'Archivo', '*.txt'))):
        cuenta.update(w.lower() for w in TOKEN.findall(open(f, encoding='utf-8', errors='ignore').read()))
    n = sum(cuenta.values())
    # bandas por logaritmo de la frecuencia: la 0 son las de siempre
    # (de, la, que), la 11 las que aparecen MIN veces
    # Solo entran las palabras que ya están en línea (web/obras/*.html):
    # partitura.json es público y no tiene que delatar borradores.
    publicas = set()
    for f in glob.glob(os.path.join(AQUI, '..', 'web', 'obras', '*.html')):
        publicas.update(w.lower() for w in TOKEN.findall(html.unescape(open(f, encoding='utf-8').read())))
    vivas = {w: c for w, c in cuenta.items() if c >= MIN}
    lmax = math.log(max(vivas.values()))
    lmin = math.log(MIN)
    b = {}
    for w, c in vivas.items():
        if w not in publicas:
            continue
        x = (lmax - math.log(c)) / (lmax - lmin or 1)
        b[w] = min(BANDAS - 1, int(x * BANDAS))
    salida = {'nota': 'Calculado por partitura.py (no se edita a mano).', 'n': n, 'bandas': BANDAS,
              'b': dict(sorted(b.items()))}
    with open(os.path.join(AQUI, 'partitura.json'), 'w', encoding='utf-8') as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'{n} palabras · {len(cuenta)} distintas · {len(b)} con banda (≥{MIN}) → partitura.json')


if __name__ == '__main__':
    main()
