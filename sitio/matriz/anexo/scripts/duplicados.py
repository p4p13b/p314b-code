"""Pasajes repetidos entre obras (mismo texto en dos libros): se deja uno solo.
Prioridad: obras ancla primero, después el orden del índice."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, os

ANCLA = ['terminos-y-condiciones', 'no-teoria', 'dos-puntos', 'potencial-de-repente-en-carnaval', 'si', 'los-nacidos', 'si-teoria']
CACHE = os.path.join(os.getcwd(), 'duplicados.json')  # carpeta de trabajo (_rutas)


def calcular():
    P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))['pasajes']
    orden = sorted(range(len(P)), key=lambda i: (0 if P[i]['obra_clave'] in ANCLA else 1,
                                                  ANCLA.index(P[i]['obra_clave']) if P[i]['obra_clave'] in ANCLA else 0, i))
    visto = {}  # shingle -> obra
    fuera = []
    for i in orden:
        p = P[i]
        w = re.findall(r'\w+', p['texto'].lower())
        sh = {' '.join(w[k:k + 8]) for k in range(max(0, len(w) - 7))}
        if not sh:
            continue
        ajenas = sum(1 for s in sh if s in visto and visto[s] != p['obra_clave'])
        if ajenas / len(sh) >= 0.5:
            fuera.append(p['id'])
            continue
        for s in sh:
            visto.setdefault(s, p['obra_clave'])
    json.dump(fuera, open(CACHE, 'w'))
    return set(fuera)


def ids_fuera():
    if os.path.exists(CACHE):
        return set(json.load(open(CACHE)))
    return calcular()


if __name__ == '__main__':
    f = calcular()
    import collections
    P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))['pasajes']
    c = collections.Counter(p['obra_clave'] for p in P if p['id'] in f)
    print(len(f), 'pasajes repetidos fuera:', c.most_common())
