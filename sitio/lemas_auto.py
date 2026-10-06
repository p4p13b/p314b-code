#!/usr/bin/env python3
"""Lemas automáticos: arma lemas-auto.json con un diccionario del español.

Recorre todo el cuerpo (los .txt de datos-lee y los capítulos de
obras/*.json) y, para cada forma que el diccionario conoce, guarda su lema.
Lo usan las tres lematizaciones (diagonal.js, matriz-superficie.js y
matriz/anexo/scripts/lematica.py), en este orden:

  1. lemas.json → formas: lo que decidiste vos. Manda siempre.
  2. los verbos irregulares de siempre (es → ser, tiene → tener…).
  3. lemas-auto.json: este archivo. Si el lema que da el diccionario está
     en tus formas, se sigue hasta el tuyo (indiferentes → indiferente →
     indiferencia).
  4. las reglas generales, para lo que el diccionario no conoce
     (acuñaciones, palabras en otros idiomas).

Los pronominales van al verbo (volverse → volver). Femenino y masculino
no se juntan (tu decisión del 30/09): si el diccionario lleva una forma en
-a/-as a un lema que no termina en -a (propias → propio), queda en femenino
singular (propia). Los verbos sí se juntan (canta → cantar).

Nada de esto toca lemas.json: es un archivo aparte, calculado, que se
puede borrar y regenerar. Lo regenera el workflow «Superficie».

Necesita: pip install simplemma (diccionario libre, sin modelos que bajar).
Uso, desde sitio/: python3 lemas_auto.py
"""
import glob
import html
import json
import os
import re
import unicodedata
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(HERE)
SALIDA = os.path.join(HERE, 'lemas-auto.json')
TOKEN = re.compile(r'[^\W\d_][^\W\d_\-]+', re.U)  # como lematica.py


def norm(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w.lower()) if unicodedata.category(c) != 'Mn')


def textos():
    for f in sorted(glob.glob(os.path.join(RAIZ, 'datos-lee', 'txt', '**', '*.txt'), recursive=True)):
        with open(f, encoding='utf-8', errors='ignore') as fh:
            yield fh.read()
    for f in sorted(glob.glob(os.path.join(HERE, 'obras', '*.json'))):
        if f.endswith('-citas.json'):
            continue
        try:
            with open(f, encoding='utf-8') as fh:
                obra = json.load(fh)
        except (OSError, ValueError):
            continue
        for ch in obra.get('chapters') or []:
            yield html.unescape(re.sub(r'<[^>]+>', ' ', ch.get('body') or ''))


# Errores del diccionario en palabras frecuentes del cuerpo (revisados a
# mano en el antes/después del 03/10). Es una corrección del instrumento,
# no una decisión de lemas: lo que la autora ponga en lemas.json manda igual.
CORRECCIONES = {
    'afuera': 'afuera', 'viva': 'vivir', 'vivas': 'vivir', 'visto': 'ver', 'vista': 'ver',
    'viste': 'ver', 'venga': 'venir', 'vengan': 'venir', 'vengas': 'venir', 'miento': 'mentir',
    'rota': 'romper', 'roto': 'romper', 'rotas': 'romper', 'rotos': 'romper',
    'entera': 'entera', 'enteras': 'entera', 'trance': 'trance', 'mere': 'mere',
}
# Pronombres: el diccionario los lleva a «yo», «tú», «él»; acá quedan como están.
PRONOMBRES = {'yo', 'tu', 'el', 'ella', 'nosotros', 'vosotros', 'ellos', 'mi', 'me', 'se', 'si'}


def preferir_sustantivo(forma, lema, conocidas):
    """flores → flor, no florar: si el singular es una palabra que el
    diccionario conoce como su propio lema, el plural va ahí."""
    if not re.search(r'(ar|er|ir)$', norm(lema)) or not forma.endswith('s'):
        return lema
    for sing in (forma[:-1], forma[:-2], forma[:-3] + 'z' if forma.endswith('ces') else None):
        if sing and len(sing) >= 3 and conocidas.get(sing) == sing:
            return sing
    return lema


def sin_pronombre(lema):
    """volverse → volver: el diccionario deja algunos pronominales aparte."""
    return lema[:-2] if re.search(r'(ar|er|ir)se$', lema) else lema


def sin_genero(forma, lema):
    """propias → propia (no propio); los verbos y lo que ya es -a quedan."""
    n, l = norm(forma), norm(lema)
    if n.endswith(('a', 'as')) and not l.endswith('a') and not l.endswith(('ar', 'er', 'ir')):
        return forma[:-1] if n.endswith('as') else forma
    return lema


def main():
    import simplemma
    formas = set()
    for t in textos():
        formas.update(w.lower() for w in TOKEN.findall(t))
    cambian, propias, dicc = {}, [], {}
    for f in sorted(formas):
        if len(f) < 3 or not simplemma.is_known(f, lang='es'):
            continue
        dicc[f] = simplemma.lemmatize(f, lang='es').lower()
    for f, l in dicc.items():
        if f in CORRECCIONES:
            l = CORRECCIONES[f]
        elif norm(l) in PRONOMBRES and norm(f) != norm(l) + 's':
            l = f
        elif re.search(r'(ar|er|ir)$', norm(l)) and simplemma.is_known(f, lang='en'):
            l = f  # page, mean, done: inglés, no un verbo en español
        else:
            l = sin_genero(f, sin_pronombre(preferir_sustantivo(f, l, dicc)))
        if l == f:
            propias.append(f)
        else:
            cambian[f] = l
    try:
        from importlib.metadata import version
        fuente = 'simplemma ' + version('simplemma')
    except Exception:
        fuente = 'simplemma'
    salida = {
        'nota': 'Calculado por lemas_auto.py: no se edita a mano. Lo que decidas va en lemas.json, '
                'que manda sobre esto. «formas»: forma → lema del diccionario; «propias»: formas '
                'que el diccionario conoce y son su propio lema.',
        'generado': date.today().isoformat(),
        'fuente': fuente,
        'formas': cambian,
        'propias': propias,
    }
    with open(SALIDA, 'w', encoding='utf-8') as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write('\n')
    print('%d formas en el cuerpo · %d con lema del diccionario · %d propias → %s'
          % (len(formas), len(cambian), len(propias), os.path.relpath(SALIDA, RAIZ)))


if __name__ == '__main__':
    main()
