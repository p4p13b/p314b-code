#!/usr/bin/env python3
"""
indexar_pasajes.py — arma el conjunto de anclas posibles de la matriz.

Uso (desde sitio/):
    python matriz/indexar_pasajes.py

Lee config.json ("universo") y escribe cache-matriz/pasajes.json, en la raíz
del repo y fuera de sitio/: contiene páginas completas de datos-lee, que no
se publica.

- PDF: cada PDF de Archivo/manifest.json que tenga su .txt en datos-lee/txt
  (se empareja por la cabecera "[<nombre>.pdf -- N pages]" del .txt). Un
  pasaje por página física (<<<PAGE N>>>) con al menos
  "pasaje_palabras_minimas" palabras.
  Solo entran los PDF que viven en el sitio (vigencia.py): el sitio del
  pasaje es el posteo que lo publica ("1021.pdf" → 1-0-2-1). Un PDF
  oculto cuyo texto se publicó escrito no entra (entra el escrito), ni un
  texto que no vive en ningún posteo. Los poemarios quedan como estaban.
  El id del pasaje sigue usando el nombre del PDF, así las decisiones ya
  tomadas siguen reconociendo sus propuestas.
- Posts: los de obras/*.json (no corpus.json, que puede tener nombres
  viejos) cuya "serie" esté en universo.series, o cuyo id esté en
  universo.posts, o todos los que están en línea si
  universo.posts_publicados es true. Un pasaje por párrafo; los párrafos cortos se
  juntan con el siguiente hasta llegar al mínimo.

Un pasaje es un lugar donde podría apoyarse una diagonal (estatuto
"verificado": solo afirma que ese texto está ahí). No es una relación.
"""
import glob
import html
import os
import re
from datetime import datetime

import vigencia
from comun import (
    DATOS_LEE_TXT, MANIFEST_PATH, PASAJES_PATH, RAIZ_DIR, SITIO_DIR,
    cargar_config, cargar_json, clave_obra, guardar_json, normalizar, slugify,
)


def txt_por_pdf():
    """nombre de PDF (clave de obra) -> (ruta .txt, páginas declaradas)."""
    out = {}
    for f in glob.glob(os.path.join(DATOS_LEE_TXT, '*', '*.txt')):
        with open(f, encoding='utf-8') as fh:
            m = re.match(r'\[(.*?) -- (\d+) pages\]', fh.readline())
        if m:
            out[clave_obra(m.group(1))] = (f, int(m.group(2)))
    return out


def paginas(path):
    with open(path, encoding='utf-8') as f:
        t = f.read()
    partes = re.split(r'<<<PAGE (\d+)>>>', t)
    return [(int(partes[i]), normalizar(partes[i + 1])) for i in range(1, len(partes), 2)]


def parrafos_de_html(body):
    bloques = re.split(r'</p>|</div>|<br\s*/?>|</h\d>|</blockquote>', body or '', flags=re.I)
    out = []
    for b in bloques:
        t = normalizar(html.unescape(re.sub(r'<[^>]+>', ' ', b)))
        if t:
            out.append(t)
    return out


def main():
    cfg = cargar_config()
    uni = cfg.get('universo') or {}
    minimo = int(cfg.get('pasaje_palabras_minimas', 25))
    taller = {}
    for ruta in sorted(glob.glob(os.path.join(SITIO_DIR, 'obras', '*.json'))):
        if not ruta.endswith('-citas.json'):
            taller[os.path.basename(ruta)[:-5]] = cargar_json(ruta, None)

    pasajes, sitios = [], {}

    if uni.get('pdfs_manifest'):
        txts = txt_por_pdf()
        vig = vigencia.calcular()['archivo']
        for nombre_pdf in cargar_json(MANIFEST_PATH, []):
            clave = clave_obra(nombre_pdf)
            slug = slugify(re.sub(r'\.pdf$', '', nombre_pdf, flags=re.I))
            if clave not in txts:
                print('  sin .txt en datos-lee:', nombre_pdf)
                continue
            path, declaradas = txts[clave]
            v = vig.get(os.path.relpath(path, RAIZ_DIR)) or {}
            if v.get('estado') not in ('vivo', 'poemario') or not v.get('vigente'):
                print('  no entra %s: %s%s' % (nombre_pdf, v.get('estado', '?'),
                                              ' (su texto es %s)' % v['vigente'] if v.get('vigente') else ''))
                continue
            sitio = v['vigente']
            n = 0
            for num, texto in paginas(path):
                if len(texto.split()) < minimo:
                    continue
                pasajes.append({'id': 'pdf:%s:p%d' % (slug, num), 'sitio': sitio, 'tipo_nodo': 'pdf',
                                'obra_clave': clave, 'pdf_pagina': num, 'texto': texto})
                n += 1
            pub = taller.get(sitio) or {}
            sitios[sitio] = {'titulo': (pub.get('book') or {}).get('title') or re.sub(r'\.pdf$', '', nombre_pdf, flags=re.I),
                             'tipo_nodo': 'pdf', 'archivo_pdf': nombre_pdf, 'paginas': declaradas, 'pasajes': n,
                             'publicado': pub.get('en_linea') is True,
                             'fuente': os.path.relpath(path, os.path.dirname(SITIO_DIR))}

    series = set(uni.get('series') or [])
    ids_posts = set(uni.get('posts') or [])
    todos = bool(uni.get('posts_publicados'))
    for oid, datos in taller.items():
        if not isinstance(datos, dict) or datos.get('tipo') == 'pdf':
            continue
        obra = {'id': oid, 'titulo': (datos.get('book') or {}).get('title') or oid,
                'serie': (datos.get('serie') or '').strip() or None, 'en_linea': datos.get('en_linea') is True}
        # posts_publicados: todos los posteos de texto marcados «mostrar en
        # el sitio web» (los no marcados, solo si se los nombra)
        if obra['id'] not in ids_posts and obra.get('serie') not in series and not (todos and obra.get('en_linea')):
            continue
        n = 0
        for ch in datos.get('chapters', []):
            acumulado, k = [], 0
            for p in parrafos_de_html(ch.get('body')):
                acumulado.append(p)
                if sum(len(x.split()) for x in acumulado) >= minimo:
                    pasajes.append({'id': 'post:%s:%s:%d' % (obra['id'], ch['id'], k), 'sitio': obra['id'],
                                    'tipo_nodo': 'post', 'obra_clave': clave_obra(obra.get('titulo')) or obra['id'],
                                    'capitulo': ch['id'], 'texto': ' '.join(acumulado)})
                    acumulado, k, n = [], k + 1, n + 1
            if acumulado and pasajes and pasajes[-1]['sitio'] == obra['id'] and pasajes[-1].get('capitulo') == ch['id']:
                pasajes[-1]['texto'] += ' ' + ' '.join(acumulado)
        sitios[obra['id']] = {'titulo': obra.get('titulo'), 'tipo_nodo': 'post', 'pasajes': n,
                              'serie': obra.get('serie'), 'publicado': obra['en_linea'], 'fuente': 'sitio/obras/%s.json' % obra['id']}

    guardar_json(PASAJES_PATH, {
        'meta': {'generado': datetime.now().isoformat(timespec='seconds'), 'universo': uni,
                 'pasaje_palabras_minimas': minimo, 'estatuto': 'verificado', 'sitios': sitios},
        'pasajes': pasajes,
    })
    print('── indexar_pasajes.py ──')
    for slug, s in sitios.items():
        extra = '' if s['tipo_nodo'] == 'post' else ' de %d páginas%s' % (s['paginas'], '' if s['publicado'] else ', PDF todavía no publicado')
        print('  %-36s %4d pasajes (%s%s)' % (slug, s['pasajes'], s['tipo_nodo'], extra))
    if not series & {(o.get('serie') or '').strip() for o in taller.values() if isinstance(o, dict)} and series:
        print('  (ningún post de las series %s en obras/ todavía)' % ', '.join(sorted(series)))
    print('\n%d pasajes de %d sitios → %s' % (len(pasajes), len(sitios), os.path.relpath(PASAJES_PATH, os.path.dirname(SITIO_DIR))))


if __name__ == '__main__':
    main()
