#!/usr/bin/env python3
"""
eliminar_obra.py

Saca una obra del sitio. Dos maneras:

    python eliminar_obra.py <slug>            # eliminar (va a la papelera)
    python eliminar_obra.py <slug> --ocultar  # solo quitarla de la web

--ocultar: le saca el tilde "mostrar en el sitio web" (en_linea) a
obras/<slug>.json. La obra sigue en el taller y en tu máquina, igual
que antes de marcarla; la próxima publicación la saca de web/.

Eliminar: mueve obras/<slug>.json a papelera/ (con fecha), junto con
las acciones de esa obra que había en acciones.json, y borra la página
generada (obras/<slug>.html), sus citas y su entrada de corpus.json.
Nada se pierde del todo: para recuperarla, copiá el .json de la
papelera de vuelta a obras/ (el taller lo abre con "cargar") y
publicala. El PDF de un posteo-PDF (Archivo/) no se toca.

Si una diagonal u hojear de un capítulo PUBLICADO de otra obra apunta
a esta, no se elimina (avisa cuáles): primero hay que editarlas. Las de
capítulos no publicados quedan como "destino roto". Después de eliminar
hay que regenerar todas las obras (lo hace el botón, o a mano:
generar_obra.py de cada una y publicar.py).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from util import leer

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG_OK = re.compile(r'^[a-z0-9-]+$')


def guardar(ruta, datos):
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write('\n')


def ocultar(slug):
    ruta = os.path.join(HERE, 'obras', slug + '.json')
    obra = leer(ruta, None)
    if not isinstance(obra, dict):
        sys.exit(f'✗ no existe obras/{slug}.json')
    if obra.get('en_linea') is not True:
        print(f'· "{slug}" ya no estaba marcada para la web.')
        return
    obra['en_linea'] = False
    guardar(ruta, obra)
    print(f'✓ "{slug}": sin el tilde "mostrar en el sitio web". Sigue en el taller.')


def eliminar(slug):
    ruta = os.path.join(HERE, 'obras', slug + '.json')
    obra = leer(ruta, None)
    if not isinstance(obra, dict):
        sys.exit(f'✗ no existe obras/{slug}.json')

    registro = leer(os.path.join(HERE, 'acciones.json'), {'acciones': {}})
    registro.setdefault('acciones', {})
    propias = {aid: a for aid, a in registro['acciones'].items()
               if (a.get('origen') or {}).get('obra') == slug}

    # 0. Si alguna diagonal u hojear de un capítulo PUBLICADO de otra obra
    #    apunta acá, no se elimina: generar_obra.py se negaría a regenerar
    #    esa otra obra. Quitarla de la web sí se puede (allá queda
    #    "destino aún no publicado").
    ids = set(propias)
    bloquean = []
    for otra in sorted(os.listdir(os.path.join(HERE, 'obras'))):
        if not otra.endswith('.json') or otra.endswith('-citas.json') or otra == slug + '.json':
            continue
        fuente = leer(os.path.join(HERE, 'obras', otra), {})
        unidades = (fuente.get('partes') if fuente.get('tipo') == 'pdf' else fuente.get('chapters')) or []
        publicados = {u.get('id') for u in unidades if u.get('estado') == 'publicada'}
        for a in registro['acciones'].values():
            if (a.get('origen') or {}).get('obra') == otra[:-5] and (a.get('origen') or {}).get('capitulo') in publicados:
                # también un hojear hacia la obra entera («obra:<slug>», «obra:<slug>#p=<n>»)
                if any(t.get('destino') in ids or (t.get('destino') or '').split('#')[0] == 'obra:' + slug
                       for t in a.get('tipos') or []):
                    bloquean.append(otra[:-5] + ' (' + a.get('id', '?') + ')')
    if bloquean:
        print('✗ No se eliminó "' + slug + '": estas acciones de capítulos publicados de otras obras apuntan acá:')
        for b in bloquean:
            print('  - ' + b)
        print('Editá esas diagonales (o bajá esos capítulos a "listo") y volvé a intentar.\n'
              'Si solo querés que no se vea, usá "quitar de la web" (--ocultar).')
        sys.exit(1)

    # 1. A la papelera: la fuente de la obra + sus acciones del registro
    #    (dentro de acciones_nuevas, así el taller las vuelve a fundir si
    #    la recuperás).
    os.makedirs(os.path.join(HERE, 'papelera'), exist_ok=True)
    copia = dict(obra)
    copia['acciones_nuevas'] = {**propias, **(obra.get('acciones_nuevas') or {})}
    copia['en_linea'] = False
    copia['_eliminada'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    destino = os.path.join(HERE, 'papelera', datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + slug + '.json')
    guardar(destino, copia)
    print(f'✓ copia en papelera/{os.path.basename(destino)}')

    # 2. Registro de acciones y corpus.json.
    for aid in propias:
        del registro['acciones'][aid]
    guardar(os.path.join(HERE, 'acciones.json'), registro)
    print(f'✓ acciones.json: {len(propias)} acción(es) de "{slug}" fuera del registro')

    corpus = leer(os.path.join(HERE, 'corpus.json'), {'obras': []})
    antes = len(corpus.get('obras') or [])
    corpus['obras'] = [o for o in corpus.get('obras') or [] if o.get('id') != slug]
    guardar(os.path.join(HERE, 'corpus.json'), corpus)
    print(f'✓ corpus.json: {antes - len(corpus["obras"])} entrada(s) quitada(s)')

    # 3. Archivos de la obra.
    for nombre in (slug + '.json', slug + '.html', slug + '-citas.json'):
        p = os.path.join(HERE, 'obras', nombre)
        if os.path.exists(p):
            os.remove(p)
            print(f'✓ borrado obras/{nombre}')

    # Diagonales de otras obras (no publicadas) que apuntaban acá.
    rotas = sorted({(a.get('origen') or {}).get('obra') or '?'
                    for a in registro['acciones'].values()
                    for t in a.get('tipos') or []
                    if t.get('destino') in ids})
    if rotas:
        print('· Ojo: estas obras tienen diagonales u hojeares que apuntaban a "' + slug + '" '
              '(quedan como destino roto hasta que los edites): ' + ', '.join(rotas))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('slug')
    ap.add_argument('--ocultar', action='store_true', help='solo quitarla de la web (no la elimina)')
    args = ap.parse_args()
    if not SLUG_OK.match(args.slug):
        sys.exit('✗ slug inválido: ' + args.slug)
    if args.ocultar:
        ocultar(args.slug)
    else:
        eliminar(args.slug)


if __name__ == '__main__':
    main()
