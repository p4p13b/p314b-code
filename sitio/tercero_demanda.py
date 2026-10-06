"""tercero_demanda.py — el tercer texto entre dos fragmentos (se corre a mano).

En el taller, la acción «tercero» une un fragmento con otro (un ancla).
Este script busca, entre los textos en línea que no son ninguno de los
dos, el pasaje que más comparte con ambos a la vez, y lo guarda en la
acción (acciones.json, campo «resultado»). Al publicar, la lectura lo
abre al costado como un hojear: «tercero entre este fragmento y …».

Cómo mide: TF-IDF sobre las palabras que cuentan (el lematizador de la
matriz), con unidades del tamaño de una página (las páginas de los PDF;
los textos de la plataforma, en tramos de ~150 palabras). La fuerza es la
media geométrica de los dos cosenos, así que gana lo que toca a los dos
fragmentos, no lo que se parece mucho a uno solo.

    python3 tercero_demanda.py          solo los que no tienen resultado
    python3 tercero_demanda.py --todo   recalcula todos
"""
import collections
import json
import math
import os
import re
import sys
from util import bloque_de

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, 'matriz', 'anexo', 'scripts'))
from publicados import textos
from generar_obra import cargar_json, guardar_json

ACCIONES = os.path.join(AQUI, 'acciones.json')
TRAMO = 150


def texto_de(origen, aid):
    """El párrafo donde está marcada la acción (aunque no esté publicado:
    esto lo corre la autora), o, en un PDF, su página."""
    obra = cargar_json(os.path.join(AQUI, 'obras', (origen.get('obra') or '') + '.json'), None) or {}
    frag = origen.get('fragmento') or ''
    if origen.get('pdf_pagina'):
        nombre = re.sub(r'\.pdf$', '.txt', ((obra.get('pdf') or {}).get('archivo') or ''), flags=re.I)
        ruta = os.path.join(AQUI, 'Archivo', nombre)
        if nombre and os.path.isfile(ruta):
            paginas = re.split(r'<<<PAGE \d+>>>', open(ruta, encoding='utf-8', errors='ignore').read())
            n = int(origen['pdf_pagina'])
            if 0 < n < len(paginas):
                return frag + ' ' + paginas[n]
        return frag
    cap = next((c for c in obra.get('chapters') or [] if c.get('id') == origen.get('capitulo')), None)
    body = (cap or {}).get('body') or ''
    m = re.search(r'data-accion="[^"]*\b%s\b[^"]*"' % re.escape(aid), body)
    if not m:
        return frag
    trozo = bloque_de(body, m)
    return frag + ' ' + re.sub(r'<[^>]+>', ' ', trozo)


def main():
    todo = '--todo' in sys.argv
    registro = cargar_json(ACCIONES, None)
    pendientes = []
    for aid, a in (registro or {}).get('acciones', {}).items():
        for t in a.get('tipos') or []:
            if t.get('tipo') == 'tercero' and t.get('destino') and (todo or not (t.get('resultado') or {}).get('obra')):
                pendientes.append((aid, a, t))
    if not pendientes:
        print('No hay terceros por buscar.')
        return
    cwd = os.getcwd()
    import lematica  # noqa: E402 (hace chdir a la carpeta de trabajo de la matriz)
    os.chdir(cwd)

    pub = textos()
    unidades = []  # (obra, pdf, página o None, texto)
    for slug, t in pub.items():
        if t['pdf']:
            for i, p in enumerate(t['partes'], 1):
                if p.strip():
                    unidades.append((slug, True, i, p))
        else:
            palabras = ' '.join(t['partes']).split()
            for i in range(0, len(palabras), TRAMO):
                unidades.append((slug, False, None, ' '.join(palabras[i:i + TRAMO + 30])))
    tfs = [collections.Counter(c for _, c in lematica.tokens(u[3])) for u in unidades]
    n = len(tfs)
    df = collections.Counter(c for tf in tfs for c in tf)
    idf = {c: math.log(n / d) for c, d in df.items()}

    def vec(tf):
        v = {c: (1 + math.log(x)) * idf.get(c, math.log(n)) for c, x in tf.items()}
        nn = math.sqrt(sum(x * x for x in v.values())) or 1
        return {c: x / nn for c, x in v.items()}
    V = [vec(tf) for tf in tfs]

    hechos = 0
    for aid, a, t in pendientes:
        oa = a.get('origen') or {}
        b = registro['acciones'].get(t['destino']) or {}
        ob = b.get('origen') or {}
        va = vec(collections.Counter(c for _, c in lematica.tokens(texto_de(oa, aid))))
        vb = vec(collections.Counter(c for _, c in lematica.tokens(texto_de(ob, t['destino']))))
        fuera = {oa.get('obra'), ob.get('obra')}
        mejor = None
        for i, u in enumerate(unidades):
            if u[0] in fuera:
                continue
            ca = sum(x * va.get(c, 0) for c, x in V[i].items())
            cb = sum(x * vb.get(c, 0) for c, x in V[i].items())
            f = math.sqrt(max(ca, 0) * max(cb, 0))
            if not mejor or f > mejor[0]:
                mejor = (f, i)
        if not mejor or mejor[0] <= 0:
            print('·', aid, ': sin tercero (los dos fragmentos no comparten nada con ningún texto en línea)')
            continue
        f, i = mejor
        slug, es_pdf, pag, txt = unidades[i]
        # la frase del tramo que más toca a los dos
        frases = [x.strip() for x in re.split(r'(?<=[.!?…])\s+', re.sub(r'\s+', ' ', txt)) if len(x.split()) >= 5] or [txt[:220]]
        def toca(x):
            v = vec(collections.Counter(c for _, c in lematica.tokens(x)))
            return sum(y * va.get(c, 0) for c, y in v.items()) + sum(y * vb.get(c, 0) for c, y in v.items())
        frase = max(frases, key=toca)
        comunes = sorted((c for c in V[i] if c in va and c in vb), key=lambda c: -V[i][c])[:6]
        t['resultado'] = {'obra': slug, 'titulo': pub[slug]['titulo'], 'pdf': es_pdf, 'p': pag,
                          'fragmento': frase[:240], 'puntaje': round(f * 100), 'comunes': comunes}
        hechos += 1
        print('✓', aid, '→', pub[slug]['titulo'] + (', p. %d' % pag if pag else ''), '(fuerza %d)' % round(f * 100), '·', ', '.join(comunes))
    if hechos:
        guardar_json(ACCIONES, registro)
        # La obra de origen es la fuente de sus acciones (acciones_nuevas):
        # generar_obra rehace acciones.json desde ahí, así que el resultado
        # va también ahí. Solo se toca el campo «resultado» de ese tercero.
        por_obra = collections.defaultdict(list)
        for aid, a, t in pendientes:
            if (t.get('resultado') or {}).get('obra'):
                por_obra[(a.get('origen') or {}).get('obra')].append((aid, t))
        for slug, lista in por_obra.items():
            ruta = os.path.join(AQUI, 'obras', (slug or '') + '.json')
            obra = cargar_json(ruta, None)
            if not obra:
                continue
            cambio = False
            for aid, t in lista:
                for x in ((obra.get('acciones_nuevas') or {}).get(aid) or {}).get('tipos') or []:
                    if x.get('tipo') == 'tercero' and x.get('destino') == t['destino']:
                        x['resultado'] = t['resultado']; cambio = True
            if cambio:
                with open(ruta, 'w', encoding='utf-8') as fh:
                    fh.write(json.dumps(obra, ensure_ascii=False, indent=2) + '\n')
        print(hechos, 'tercero(s) guardado(s). Publicá para que se vean.')


if __name__ == '__main__':
    main()
