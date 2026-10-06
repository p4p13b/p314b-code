#!/usr/bin/env python3
"""
sincronizar_textos_pdf.py

El texto de cada posteo-PDF vive en datos-lee/txt (ahí se edita). Las
páginas y scripts que leen el texto de un PDF (generar_obra, partitura,
publicados, tercero_demanda y las vistas de la matriz, que solo leen
dentro de sitio/) lo toman de Archivo/<nombre>.txt: este paso lo regenera
desde datos-lee/txt, para que haya una sola transcripción. No se edita a
mano Archivo/*.txt de un PDF que tenga texto en datos-lee/txt. Un PDF sin
texto allá conserva el que tenga en Archivo/.

El texto de los posteos escritos a mano no pasa por acá: sale de
obras/<slug>.json.
"""
import glob
import os
import re

from util import slugify

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(HERE, 'Archivo')
TXT = os.path.join(HERE, '..', 'datos-lee', 'txt')


def clave(nombre):
    return re.sub(r'[^a-z0-9]+', '', slugify(nombre))


def textos_de_datos_lee():
    """{clave del nombre del PDF: ruta}, por la cabecera «[X.pdf -- N pages]»."""
    out = {}
    for f in sorted(glob.glob(os.path.join(TXT, '*', '*.txt'))):
        with open(f, encoding='utf-8') as fh:
            m = re.match(r'\[(.*?) -- \d+ pages\]', fh.readline())
        if not m:
            continue
        nombre = re.sub(r'^\s*([IVX]+|\d+)\s*-\s*', '',
                        re.sub(r'\.(docx\.)?pdf$', '', m.group(1), flags=re.I))
        if clave(nombre):
            out.setdefault(clave(nombre), f)
    return out


def main():
    fuentes = textos_de_datos_lee()
    cambiados = []
    for pdf in sorted(glob.glob(os.path.join(ARCHIVO, '*.pdf'))):
        base = os.path.splitext(pdf)[0]
        origen = fuentes.get(clave(os.path.basename(base)))
        if not origen:
            continue
        with open(origen, encoding='utf-8') as fh:
            texto = fh.read()
        i = texto.find('<<<PAGE ')
        texto = texto[i:] if i >= 0 else texto   # sin la cabecera «[X.pdf -- N pages]»
        destino = base + '.txt'
        actual = open(destino, encoding='utf-8').read() if os.path.exists(destino) else None
        if texto != actual:
            with open(destino, 'w', encoding='utf-8', newline='') as fh:
                fh.write(texto)
            cambiados.append(os.path.basename(destino))
    print(f'Archivo/*.txt desde datos-lee/txt: {len(cambiados)} actualizados')


if __name__ == '__main__':
    main()
