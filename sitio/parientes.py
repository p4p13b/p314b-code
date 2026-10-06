"""parientes.py — familias de palabras y su genealogía, para la lectura (lo
corre publicar.py después de armar web/; usa pulenta/datos/familias.json).

Lo leen dos opciones de «otras lecturas» (lectura-extra.js):
  · parientes: tocar una palabra muestra su familia (las subfamilias que el
    uso une o separa) y su genealogía (en qué textos aparece cada miembro,
    por fecha de escritura);
  · mismizar: un párrafo se recompone con los parientes de sus palabras.

Toma las familias de pulenta/datos/familias.json y cuenta las apariciones
solo en lo que está en línea (publicados.py). Escribe parientes.json:
  { "o": [[slug, título, fecha], ...],                    obras, por fecha
    "f": [{ "r": raíz,
            "s": [[miembro, ...], ...],                    subfamilias de uso
            "m": { miembro: { "p": primera aparición en el corpus (año-mes),
                              "g": [[obra, n], ...] } } }],
    "u": { forma: [familia, miembro] } }                    forma → su familia

    python3 parientes.py
"""
import collections
import json
import os
import re

from publicados import textos, RAIZ

AQUI = os.path.dirname(os.path.abspath(__file__))
FAMILIAS = os.path.join(RAIZ, 'pulenta', 'datos', 'familias.json')
TOKEN = re.compile(r'[^\W\d_]+(?:-[^\W\d_]+)*', re.U)


def main():
    pub = textos()
    orden = sorted(pub, key=lambda s: (pub[s]['fecha'] or '9', s))
    idx = {s: i for i, s in enumerate(orden)}
    cuenta = {s: collections.Counter(w.lower() for p in pub[s]['partes'] for w in TOKEN.findall(p)) for s in orden}
    total = collections.Counter()
    for c in cuenta.values():
        total.update(c)

    fams = json.load(open(FAMILIAS, encoding='utf-8'))['familias']
    salida_f, u = [], {}
    for f in fams:
        miembros, nombre = {}, {}
        for m in f['miembros']:
            formas = [x.lower() for x in (m.get('formas') or [m['forma']])]
            formas = [x for x in formas if total.get(x)]
            if not formas:
                continue
            g = []
            for s in orden:
                n = sum(cuenta[s].get(x, 0) for x in formas)
                if n:
                    g.append([idx[s], n])
            # el nombre del miembro es su unidad (la decisión de la autora en
            # lemas.json: indiferente → indiferencia), no la forma más usada
            miembros[m['lema']] = {'p': m.get('primera') or '', 'g': g, '_formas': formas}
            nombre[m['forma']] = m['lema']
        if len(miembros) < 2:
            continue
        subs = [[nombre.get(x, x) for x in grupo if nombre.get(x, x) in miembros] for grupo in f.get('subfamilias_uso') or []]
        subs = [s for s in subs if s]
        sueltos = [x for x in miembros if not any(x in s for s in subs)]
        subs += [[x] for x in sueltos]
        fi = len(salida_f)
        for forma, d in miembros.items():
            for x in d.pop('_formas'):
                u.setdefault(x, [fi, forma])
        salida_f.append({'r': f['raiz'], 's': subs, 'm': miembros})

    salida = {'nota': 'Calculado por parientes.py (no se edita a mano): familias de pulenta, contadas en lo que está en línea.',
              'o': [[s, pub[s]['titulo'], pub[s]['fecha']] for s in orden], 'f': salida_f, 'u': u}
    with open(os.path.join(AQUI, 'parientes.json'), 'w', encoding='utf-8') as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(orden)} textos en línea · {len(salida_f)} familias · {len(u)} formas → parientes.json')


if __name__ == '__main__':
    main()
