#!/usr/bin/env python3
"""
actualizar_archivo.py

Escanea sitio/Archivo/ y escribe Archivo/manifest.json — la lista de
PDFs que el uploader (paso "posteo desde PDF") y cualquier otra página
del sitio pueden ofrecer para elegir, sin depender de listado de
directorio del servidor (que no existe en hosting estático real, tipo
Cloudflare — python -m http.server sí lo hace, pero eso es solo para
desarrollo local).

Corré esto cada vez que agregues o saques un PDF de Archivo/.

Uso:
    python actualizar_archivo.py
"""
import json
import os
import sys

# Windows con consola no-UTF-8 (cp1252/cp437, típico en cmd.exe o
# PowerShell sin chcp 65001): los símbolos que este script imprime
# (✓, ✗, ⚠, ·) tiran UnicodeEncodeError y cortan la corrida. Se fuerza
# UTF-8 en stdout/stderr al arrancar.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DIR = os.path.join(HERE, 'Archivo')
MANIFEST_PATH = os.path.join(ARCHIVO_DIR, 'manifest.json')


def main():
    os.makedirs(ARCHIVO_DIR, exist_ok=True)
    pdfs = sorted(f for f in os.listdir(ARCHIVO_DIR) if f.lower().endswith('.pdf'))
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(pdfs, f, ensure_ascii=False, indent=2)
    print(f'{len(pdfs)} PDF(s) en Archivo/:')
    for p in pdfs:
        print(f'  · {p}')
    print(f'\n✓ Escrito {MANIFEST_PATH}')


if __name__ == '__main__':
    main()
