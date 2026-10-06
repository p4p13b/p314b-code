"""cadaver.py — frases para el cadáver exquisito del corpus (lo corre publicar.py
después de armar web/; también se puede correr a mano).

cadaver.html arma en cada visita un texto nuevo: una frase de cada texto
en línea, encadenadas por vecindad (cada frase lleva a otra, de otro
texto, con la que comparte palabras con peso). Este script elige las
frases y calcula sus vecinas; la página solo tira los dados.

Toma hasta POR_OBRA frases de cada texto en línea (publicados.py), de
largo medio, repartidas a lo largo del texto. Vecindad: coseno TF-IDF
sobre las palabras que cuentan (lematica.py, el mismo lematizador del
resto de la matriz); se guardan las K más cercanas de OTROS textos.
Escribe cadaver.json:
  { "o": [[slug, título], ...],
    "f": [[obra, "frase", [vecina, peso%], [vecina, peso%], ...], ...] }

    python3 cadaver.py
"""
import collections
import json
import math
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, 'matriz', 'anexo', 'scripts'))
from publicados import textos  # noqa: E402

POR_OBRA = 50
K = 8
MIN_PAL, MAX_PAL = 8, 42
FRASE = re.compile(r'[^.!?…]+[.!?…]+["»”)]?', re.S)


def frases(partes):
    salida = []
    for p in partes:
        p = re.sub(r'\s+', ' ', p.replace('­', ''))
        for m in FRASE.finditer(p):
            # sin numeración de poemas o secciones al principio (XVI, 000, 3.)
            f = re.sub(r'^(?:(?:[IVXLCDM]+|\d+)[.)]?\s+)+', '', m.group().strip())
            n = len(f.split())
            letras = sum(c.isalpha() for c in f)
            if MIN_PAL <= n <= MAX_PAL and letras > 0.7 * len(f.replace(' ', '')) and f[0].isalpha():
                salida.append(f)
    return salida


def main():
    cwd = os.getcwd()
    import lematica  # noqa: E402 (hace chdir a la carpeta de trabajo de la matriz)
    os.chdir(cwd)
    pub = textos()
    obras = sorted(pub)
    lista = []  # (obra, frase, {clave: tf})
    for oi, s in enumerate(obras):
        fs = frases(pub[s]['partes'])
        if not fs:
            continue
        paso = max(1, len(fs) / POR_OBRA)
        elegidas = [fs[int(i * paso)] for i in range(min(POR_OBRA, len(fs)))]
        for f in elegidas:
            tf = collections.Counter(c for _, c in lematica.tokens(f))
            if len(tf) >= 3:
                lista.append((oi, f, tf))
    n = len(lista)
    df = collections.Counter(c for _, _, tf in lista for c in tf)
    idf = {c: math.log(n / d) for c, d in df.items()}
    vec = []
    for _, _, tf in lista:
        v = {c: (1 + math.log(x)) * idf[c] for c, x in tf.items() if df[c] >= 2}
        nn = math.sqrt(sum(x * x for x in v.values())) or 1
        vec.append({c: x / nn for c, x in v.items()})
    # índice invertido (sin las claves demasiado comunes, que no distinguen)
    inv = collections.defaultdict(list)
    for i, v in enumerate(vec):
        for c, x in v.items():
            if df[c] <= n * 0.05:
                inv[c].append((i, x))
    salida = []
    for i, v in enumerate(vec):
        acum = collections.defaultdict(float)
        for c, x in v.items():
            for j, y in inv.get(c, ()):
                if lista[j][0] != lista[i][0]:
                    acum[j] += x * y
        mejores = sorted(acum.items(), key=lambda kv: -kv[1])[:K]
        salida.append([lista[i][0], lista[i][1]] + [[j, round(p * 100)] for j, p in mejores if p >= 0.05])
    datos = {'nota': 'Calculado por cadaver.py (no se edita a mano): frases de lo que está en línea y sus vecinas.',
             'o': [[s, pub[s]['titulo']] for s in obras], 'f': salida}
    with open(os.path.join(AQUI, 'cadaver.json'), 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False, separators=(',', ':'))
    con = sum(1 for x in salida if len(x) > 2)
    print(f'{len(obras)} textos · {n} frases · {con} con vecinas → cadaver.json')


if __name__ == '__main__':
    main()
