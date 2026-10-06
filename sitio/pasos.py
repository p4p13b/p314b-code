#!/usr/bin/env python3
"""
pasos.py

La secuencia que arma el sitio, escrita una sola vez. La usan:
- «Publicar sitio» (.github/workflows/publicar.yml) y «Comprobar el
  sitio» (comprobar.yml): corren `python pasos.py`, todos los pasos;
- servidor.py (el ⚡ publicar local): solo los pasos marcados `local`,
  para que el botón no tarde (matriz/cowork.py lleva un par de minutos).

Así una PR que pasa la comprobación corrió exactamente lo mismo que va a
correr la publicación.

Orden:
  1. sincronizar_cronologia.py y sincronizar_textos_pdf.py (cortan si fallan)
     tender_decisiones.py         (si falla, avisa y sigue)
  2. generar_obra.py de cada obra (la indicada con --obra primero: si
                                   esa falla, corta; las demás solo avisan)
  3. recalcular_subgrafo.py, matriz/recalibrar.py,
     matriz/calcular_recorridos.py, crear_obras_pdf.py, matriz/cowork.py
     y publicar.py                (cualquiera que falle corta)

Uso (desde sitio/ o desde cualquier carpeta):
    python pasos.py               # todo, como en GitHub
    python pasos.py --obra SLUG   # SLUG primero
"""
import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (script, si corta al fallar, si lo corre también el ⚡ local)
ANTES = [
    # copia CRONOLOGIA.md de datos-lee/ a matriz/anexo/ (la página la lee ahí)
    ('sincronizar_cronologia.py', True, True),
    # Archivo/<pdf>.txt desde datos-lee/txt (una sola transcripción por PDF)
    ('sincronizar_textos_pdf.py', True, True),
    ('tender_decisiones.py', False, False),
]
DESPUES = [
    ('recalcular_subgrafo.py', True, True),
    # pesos de los instrumentos y recorridos (solo necesitan acciones.json
    # y corpus.json; las propuestas no, ver matriz/LEEME.md)
    (os.path.join('matriz', 'recalibrar.py'), True, True),
    (os.path.join('matriz', 'calcular_recorridos.py'), True, True),
    # un posteo-PDF por cada PDF nuevo de Archivo/ (sin publicar)
    ('crear_obras_pdf.py', True, False),
    # sugerencias de cada parte nueva del cuerpo hacia el archivo
    (os.path.join('matriz', 'cowork.py'), True, False),
    ('publicar.py', True, True),   # arma web/ (lo que publica Cloudflare)
]


def todas_las_obras():
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(HERE, 'obras', '*.json'))
                  if not p.endswith('-citas.json'))


def aviso(titulo, texto):
    if os.environ.get('GITHUB_ACTIONS'):
        print(f'::warning title={titulo}::{texto}', flush=True)
    else:
        print(f'⚠ {titulo}: {texto}', flush=True)


def correr(script, *args):
    print(f'$ python {script} {" ".join(args)}'.rstrip(), flush=True)
    return subprocess.run([sys.executable, script, *args], cwd=HERE).returncode == 0


def main():
    ap = argparse.ArgumentParser(description='Arma el sitio: todos los pasos, en orden.')
    ap.add_argument('--obra', default='', help='slug de obras/<slug>.json a generar primero')
    a = ap.parse_args()
    if a.obra and not re.fullmatch(r'[a-z0-9-]+', a.obra):
        sys.exit(f'slug inválido: {a.obra}')

    for script, corta, _ in ANTES:
        if not correr(script):
            if corta:
                sys.exit(1)
            aviso(script, 'no se pudo correr (ver el error arriba); sigue')

    # Siempre todas las obras (tarda segundos): así ninguna queda atrasada
    # si una publicación anterior se canceló o falló. Una obra con un
    # problema propio no frena a las demás; solo corta la indicada.
    if a.obra and os.path.exists(os.path.join(HERE, 'obras', a.obra + '.json')):
        if not correr('generar_obra.py', os.path.join('obras', a.obra + '.json')):
            sys.exit(1)
    fallidas = []
    for slug in todas_las_obras():
        if not correr('generar_obra.py', os.path.join('obras', slug + '.json')):
            fallidas.append(slug)
            aviso('Obra sin regenerar', f'obras/{slug}.json quedó como estaba (ver el error arriba)')
    if fallidas:
        print('Sin regenerar: ' + ' '.join(fallidas))

    for script, corta, _ in DESPUES:
        if not correr(script):
            if corta:
                sys.exit(1)
            aviso(script, 'no se pudo correr (ver el error arriba); sigue')


if __name__ == '__main__':
    main()
