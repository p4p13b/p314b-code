"""publicados.py — el texto de lo que está en línea, para los scripts que
arman datos públicos (parientes.py, cadaver.py).

Lee web/ (lo que armó publicar.py): de cada texto escrito en la plataforma,
sus capítulos tal como están publicados; de cada posteo-PDF, la
transcripción de su PDF (Archivo/*.txt), que ya es público. Así nada de
lo que estos scripts escriben puede delatar un borrador.

    from publicados import textos
    for slug, t in textos().items():  t = {'titulo', 'fecha', 'pdf', 'partes': [str, ...]}
"""
import html
import json
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
WEB = os.path.join(RAIZ, 'web')
DATOS_PULENTA = os.path.join(RAIZ, 'pulenta', 'datos', 'obras.json')


def sin_html(s):
    s = re.sub(r'<(br|/p|/li|/h\d|/blockquote)\b[^>]*>', '\n', s or '', flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', ' ', s))


def fechas():
    """Fecha de escritura de cada obra (pulenta/datos/obras.json); si no está,
    la de corpus.json (que es la de carga)."""
    f = {}
    try:
        d = json.load(open(DATOS_PULENTA, encoding='utf-8'))
        for slug, o in (d.get('obras') or {}).items():
            if o.get('fecha'):
                f[slug] = o['fecha']
    except (OSError, ValueError):
        pass
    return f


def textos():
    corpus = json.load(open(os.path.join(WEB, 'corpus.json'), encoding='utf-8'))
    fe = fechas()
    salida = {}
    for o in corpus.get('obras') or []:
        if o.get('diagonal') or o.get('en_linea') is False:
            continue
        slug = o['id']
        ruta = os.path.join(WEB, 'obras', o.get('_file') or slug + '.html')
        if not os.path.isfile(ruta):
            continue
        partes = []
        if o.get('tipo_nodo') == 'pdf' or o.get('_pdfArchivo'):
            nombre = re.sub(r'\.pdf$', '.txt', o.get('_pdfArchivo') or '', flags=re.I)
            txt = os.path.join(AQUI, 'Archivo', nombre)
            if nombre and os.path.isfile(txt):
                partes = [p for p in re.split(r'<<<PAGE \d+>>>', open(txt, encoding='utf-8', errors='ignore').read()) if p.strip()]
        else:
            h = open(ruta, encoding='utf-8').read()
            m = re.search(r'const CHAPTERS = (\[.*?\]);\n', h, re.S)
            if m:
                try:
                    partes = [sin_html(c.get('body')) for c in json.loads(m.group(1))]
                except ValueError:
                    partes = []
        if partes:
            salida[slug] = {'titulo': o.get('titulo') or slug, 'fecha': fe.get(slug) or o.get('fecha_creacion') or '',
                            'pdf': bool(o.get('_pdfArchivo')), 'partes': partes}
    return salida
