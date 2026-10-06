#!/usr/bin/env python3
"""Comprueba web/ antes de que llegue a p314b.space.

Dos partes:

1. Sin navegador (rápida, siempre):
   - todos los .json de web/ se leen;
   - ninguna página publicada tiene un token de plantilla sin reemplazar
     (___TITULO___, ___CHAPTERSDATA___…); el taller sí los lleva, porque
     los reemplaza él mismo al previsualizar;
   - corpus.json no repite ids ni archivos, y cada obra tiene su página;
   - las fuentes de sitio/obras/ se leen (un .json roto deja a su obra
     sin regenerar sin que nadie lo note).

2. Con navegador (--navegador): sirve web/ en local y abre el índice, el
   mapa y tres obras (dos escritas y un PDF) en Chromium. Falla si alguna
   tira un error de JavaScript. Necesita `pip install playwright`.

Uso, desde la raíz del repo (después de correr sitio/publicar.py):
    python3 tests/comprobar_web.py
    python3 tests/comprobar_web.py --navegador
Sale con código 1 si encuentra algo, y dice qué y dónde.
"""
import argparse
import functools
import glob
import http.server
import json
import os
import re
import sys
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, 'web')
OBRAS_FUENTE = os.path.join(RAIZ, 'sitio', 'obras')

TOKEN = re.compile(r'___[A-Z][A-Z0-9_]*___')
# Páginas que llevan los tokens a propósito: los reemplazan en el navegador.
CON_TOKENS = {'uploader-v1.html'}

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass


def rel(p):
    return os.path.relpath(p, RAIZ)


def revisar_json(errores):
    for ruta in glob.glob(os.path.join(WEB, '**', '*.json'), recursive=True):
        try:
            with open(ruta, encoding='utf-8') as f:
                json.load(f)
        except (ValueError, UnicodeDecodeError) as e:
            errores.append(f'{rel(ruta)}: JSON inválido ({e})')


def revisar_tokens(errores):
    for ruta in glob.glob(os.path.join(WEB, '**', '*.html'), recursive=True):
        if os.path.basename(ruta) in CON_TOKENS:
            continue
        with open(ruta, encoding='utf-8', errors='replace') as f:
            hallados = sorted(set(TOKEN.findall(f.read())))
        if hallados:
            errores.append(f'{rel(ruta)}: tokens sin reemplazar {", ".join(hallados)}')


def revisar_corpus(errores):
    ruta = os.path.join(WEB, 'corpus.json')
    try:
        with open(ruta, encoding='utf-8') as f:
            obras = json.load(f)['obras']
    except (OSError, ValueError, KeyError) as e:
        errores.append(f'web/corpus.json: no se puede leer la lista de obras ({e})')
        return
    ids, archivos = {}, {}
    for o in obras:
        oid, arch = o.get('id'), o.get('_file')
        if oid in ids:
            errores.append(f'web/corpus.json: el id «{oid}» está dos veces')
        ids[oid] = True
        if arch:
            if arch in archivos:
                errores.append(f'web/corpus.json: «{oid}» y «{archivos[arch]}» usan el mismo archivo {arch}')
            archivos[arch] = oid
            if not os.path.exists(os.path.join(WEB, 'obras', arch)):
                errores.append(f'web/corpus.json: «{oid}» apunta a obras/{arch}, que no está en web/')
    if not obras:
        errores.append('web/corpus.json: no hay ninguna obra en línea')


def revisar_fuentes(errores):
    for ruta in sorted(glob.glob(os.path.join(OBRAS_FUENTE, '*.json'))):
        try:
            with open(ruta, encoding='utf-8') as f:
                json.load(f)
        except (ValueError, UnicodeDecodeError) as e:
            errores.append(f'{rel(ruta)}: JSON inválido ({e})')


def elegir_paginas():
    """Índice, mapa y tres obras: las dos escritas con más diagonales y un PDF."""
    paginas = ['index.html', 'mapa.html']
    try:
        with open(os.path.join(WEB, 'corpus.json'), encoding='utf-8') as f:
            obras = json.load(f)['obras']
    except (OSError, ValueError, KeyError):
        return paginas
    escritas = sorted((o for o in obras if o.get('tipo_nodo') != 'pdf' and o.get('_file')),
                      key=lambda o: -(o.get('_totalDiags') or 0))
    pdfs = [o for o in obras if o.get('tipo_nodo') == 'pdf' and o.get('_file')]
    for o in escritas[:2] + pdfs[:1]:
        paginas.append('obras/' + o['_file'])
    return paginas


class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def revisar_navegador(errores):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        errores.append('--navegador necesita playwright (pip install playwright)')
        return
    servidor = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Silencioso, directory=WEB))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{servidor.server_address[1]}/'
    opciones = {}
    # En la nube de Claude Chromium ya está instalado aparte.
    for cand in ('/opt/pw-browsers/chromium-1194/chrome-linux/chrome',):
        if os.path.exists(cand):
            opciones['executable_path'] = cand
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(**opciones)
            for pagina in elegir_paginas():
                ctx = nav.new_context(viewport={'width': 1280, 'height': 900})
                pg = ctx.new_page()
                propios = []
                pg.on('pageerror', lambda e, propios=propios: propios.append(f'excepción: {e}'))

                def consola(m, propios=propios):
                    if m.type != 'error':
                        return
                    # Las rutas /api/ las atiende el Worker en Cloudflare, no
                    # este servidor local: que fallen acá es lo esperado.
                    url = (m.location or {}).get('url', '')
                    if '/api/' in url or 'Failed to load resource' in m.text:
                        return
                    propios.append(f'consola: {m.text}')
                pg.on('console', consola)
                try:
                    pg.goto(base + pagina, wait_until='load', timeout=30000)
                    pg.wait_for_timeout(1500)
                except Exception as e:  # noqa: BLE001  (cualquier fallo de carga es un hallazgo)
                    propios.append(f'no cargó: {e}')
                for m in propios:
                    errores.append(f'web/{pagina}: {m}')
                print(f'  {"✗" if propios else "✓"} {pagina}')
                ctx.close()
            nav.close()
    finally:
        servidor.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--navegador', action='store_true', help='abrir también páginas en Chromium')
    args = ap.parse_args()
    if not os.path.isdir(WEB):
        print('No hay web/: correr antes sitio/publicar.py')
        return 1
    errores = []
    revisar_json(errores)
    revisar_tokens(errores)
    revisar_corpus(errores)
    revisar_fuentes(errores)
    print(f'Sin navegador: {"✗" if errores else "✓"}')
    if args.navegador:
        revisar_navegador(errores)
    if errores:
        print(f'\n{len(errores)} problema(s):')
        for e in errores:
            print('  ✗ ' + e)
        return 1
    print('web/ está bien.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
