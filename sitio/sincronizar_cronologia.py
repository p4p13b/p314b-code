#!/usr/bin/env python3
"""
sincronizar_cronologia.py

CRONOLOGIA.md de la autora vive en datos-lee/cowork/ (ahí se edita). La
página matriz-anexo.html la lee de matriz/anexo/, porque solo lee dentro
de sitio/. Este paso copia la primera a la segunda para que nunca se
desfasen: no se edita la copia de matriz/anexo/.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ORIGEN = os.path.join(HERE, '..', 'datos-lee', 'cowork', 'CRONOLOGIA.md')
DESTINO = os.path.join(HERE, 'matriz', 'anexo', 'CRONOLOGIA.md')


def main():
    if not os.path.exists(ORIGEN):
        raise SystemExit(f'falta {os.path.normpath(ORIGEN)}')
    with open(ORIGEN, 'rb') as f:
        nuevo = f.read()
    actual = open(DESTINO, 'rb').read() if os.path.exists(DESTINO) else None
    if nuevo != actual:
        shutil.copyfile(ORIGEN, DESTINO)
        print('CRONOLOGIA.md: copia de matriz/anexo/ actualizada')


if __name__ == '__main__':
    main()
