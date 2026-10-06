#!/usr/bin/env python3
"""
crear_obras_pdf.py

Crea un posteo-PDF por cada PDF de Archivo/ que todavía no tenga obra.
Lo corre solo la publicación (workflow) cada vez que subís PDFs a
sitio/Archivo/; también se puede correr a mano desde sitio/:

    python crear_obras_pdf.py            # crea las que falten y las genera
    python crear_obras_pdf.py --lista    # solo muestra qué crearía

Antes de crear nada, ordena Archivo/:
- borra los .docx y .jpg/.jpeg (restos);
- saca la numeración del nombre ("5 - 1021.pdf" → "1021.pdf"), en PDFs
  y txt, y actualiza las obras que apuntaban al nombre viejo;
- un txt con el mismo nombre que un PDF queda como su texto "atrás"
  (pdf.texto): no se publica, sirve para buscar y marcar sin leer el PDF.

Los PDFs listados en Archivo/sin_obra.json no generan obra (por ejemplo,
«no teoría.pdf»: su Segunda parte va como nt2.pdf y el resto, escrito).

Cada obra nueva queda así:
- título: el nombre del archivo, sin el número de orden ("5 - 1021.pdf"
  → "1021"); si ya existe una obra con ese nombre (p. ej. la versión de
  texto), se le agrega " (PDF)" para no pisarla;
- categoría: el libro de LeE al que pertenece (Estudio, Labios, Luna,
  Póstumos, No, 0), si aparece en datos-lee/txt;
- una sola parte que abarca todas las páginas, en "borrador";
- sin el tilde "mostrar en el sitio web": no se publica hasta que lo
  marques en el taller.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(HERE, 'Archivo')
OBRAS = os.path.join(HERE, 'obras')
TXT = os.path.join(HERE, '..', 'datos-lee', 'txt')
LIBROS = {'I': 'I · Estudio', 'II': 'II · Labios', 'III': 'III · Luna', 'IV': 'IV · Póstumos', 'V': 'V · No', 'VI': 'VI · 0'}


def slugify(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def sin_numero(nombre):
    # "5 - 1021" → "1021"; "VII - sí teoría" → "sí teoría"
    return re.sub(r'^\s*([0-9]+|[IVXLC]+)\s*-\s*', '', nombre).strip()


def paginas(ruta):
    try:
        import pypdf  # noqa: WPS433
        return len(pypdf.PdfReader(ruta).pages)
    except Exception:  # noqa: BLE001 — sin pypdf, se cuenta a mano
        with open(ruta, 'rb') as f:
            datos = f.read()
        m = re.findall(rb'/Type\s*/Pages\b[^>]*?/Count\s+(\d+)', datos)
        if m:
            return max(int(x) for x in m)
        return len(re.findall(rb'/Type\s*/Page\b(?!s)', datos)) or 1


def libro_de(titulo):
    """El libro de LeE cuyo txt tiene este título (por nombre)."""
    clave = slugify(titulo)
    for d in glob.glob(os.path.join(TXT, '*-txt')):
        romano = os.path.basename(d).split('-')[0]
        for f in os.listdir(d):
            if slugify(sin_numero(os.path.splitext(f)[0].replace('.docx', ''))) == clave:
                return LIBROS.get(romano)
    return None


LICENCIA = '© Pepi · CC BY-NC-ND 4.0 — https://creativecommons.org/licenses/by-nc-nd/4.0/deed.es'


def firmar_pdfs(lista):
    """Autoría y licencia en los metadatos de cada PDF (una sola vez)."""
    try:
        from pypdf import PdfReader, PdfWriter  # noqa: WPS433
    except Exception:  # noqa: BLE001
        print('⚠ Sin pypdf: los PDFs quedan sin metadatos de licencia.')
        return
    for ruta in sorted(glob.glob(os.path.join(ARCHIVO, '*.pdf'))):
        try:
            info = PdfReader(ruta).metadata or {}
            if info.get('/Rights') == LICENCIA:
                continue
            print(f'© {os.path.basename(ruta)}: autoría y licencia en los metadatos')
            if lista:
                continue
            # Incremental: se agrega la info al final, el PDF no se reescribe.
            w = PdfWriter(ruta, incremental=True)
            nuevos = {'/Rights': LICENCIA, '/Copyright': LICENCIA, '/Author': 'Pepi'}
            if not info.get('/Title'):
                nuevos['/Title'] = os.path.splitext(os.path.basename(ruta))[0]
            w.add_metadata(nuevos)
            tmp = ruta + '.tmp'
            with open(tmp, 'wb') as f:
                w.write(f)
            if len(PdfReader(tmp).pages) != len(PdfReader(ruta).pages):
                os.remove(tmp)
                print(f'⚠ {os.path.basename(ruta)}: quedó distinto, no se toca.')
                continue
            os.replace(tmp, ruta)
        except Exception as e:  # noqa: BLE001 — un PDF raro no frena el resto
            print(f'⚠ {os.path.basename(ruta)}: no se pudo firmar ({e}).')


def obras_existentes():
    por_archivo, slugs = {}, set()
    for ruta in glob.glob(os.path.join(OBRAS, '*.json')):
        if ruta.endswith('-citas.json'):
            continue
        slug = os.path.splitext(os.path.basename(ruta))[0]
        slugs.add(slug)
        try:
            with open(ruta, encoding='utf-8') as f:
                o = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        a = (o.get('pdf') or {}).get('archivo')
        if a:
            por_archivo[a] = slug
    return por_archivo, slugs


RESTOS = ('.docx', '.jpg', '.jpeg')
# PDFs que están en Archivo/ pero no llevan posteo propio (la autora usa
# otra versión). Se edita en Archivo/sin_obra.json: una lista de nombres.
def sin_obra():
    try:
        with open(os.path.join(ARCHIVO, 'sin_obra.json'), encoding='utf-8') as f:
            return set(json.load(f))
    except (OSError, json.JSONDecodeError):
        return set()


def ordenar_archivo(lista):
    """Borra restos y saca la numeración de los nombres. Devuelve {viejo: nuevo}."""
    renombres = {}
    for ruta in sorted(glob.glob(os.path.join(ARCHIVO, '*'))):
        nombre = os.path.basename(ruta)
        base, ext = os.path.splitext(nombre)
        if ext.lower() in RESTOS:
            print(f'- {nombre} (resto, se borra)')
            if not lista:
                os.remove(ruta)
            continue
        if ext.lower() not in ('.pdf', '.txt'):
            continue
        limpio = sin_numero(base) + ext.lower()
        if limpio == nombre or not sin_numero(base):
            continue
        if os.path.exists(os.path.join(ARCHIVO, limpio)):
            print(f'⚠ {nombre}: ya existe "{limpio}", queda como está.')
            continue
        print(f'~ {nombre} → {limpio}')
        renombres[nombre] = limpio
        if not lista:
            os.rename(ruta, os.path.join(ARCHIVO, limpio))
    return renombres


def actualizar_obras(renombres, lista):
    """Obras que apuntaban a un PDF renombrado, o que tienen txt nuevo al lado."""
    for ruta in glob.glob(os.path.join(OBRAS, '*.json')):
        if ruta.endswith('-citas.json'):
            continue
        try:
            with open(ruta, encoding='utf-8') as f:
                o = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        pdf = o.get('pdf') or {}
        a = pdf.get('archivo')
        if not a:
            continue
        nuevo = renombres.get(a, a)
        texto = os.path.splitext(nuevo)[0] + '.txt'
        texto = texto if os.path.exists(os.path.join(ARCHIVO, texto)) or texto in renombres.values() else pdf.get('texto')
        if nuevo == a and texto == pdf.get('texto'):
            continue
        pdf['archivo'], o['pdf'] = nuevo, pdf
        if texto:
            pdf['texto'] = texto
        print(f'~ obras/{os.path.basename(ruta)}: pdf {nuevo}' + (f', texto {texto}' if texto else ''))
        if not lista:
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(o, f, ensure_ascii=False, indent=2)
                f.write('\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lista', action='store_true')
    args = ap.parse_args()
    renombres = ordenar_archivo(args.lista)
    actualizar_obras(renombres, args.lista)
    firmar_pdfs(args.lista)
    if not args.lista:  # manifest al día para el taller
        subprocess.run([sys.executable, 'actualizar_archivo.py'], cwd=HERE, capture_output=True)
    por_archivo, slugs = obras_existentes()
    saltear = sin_obra()
    nuevas = []
    pdfs = sorted(glob.glob(os.path.join(ARCHIVO, '*.pdf')))
    if args.lista:  # en la prueba los archivos no se renombraron
        viejos = {os.path.join(ARCHIVO, v): os.path.join(ARCHIVO, n) for v, n in renombres.items()}
        pdfs = sorted(viejos.get(r, r) for r in pdfs)
    for ruta in pdfs:
        archivo = os.path.basename(ruta)
        if archivo in por_archivo or archivo in saltear:
            continue
        titulo = sin_numero(os.path.splitext(archivo)[0])
        if slugify(titulo) in slugs:
            titulo += ' (PDF)'
        slug = slugify(titulo)
        real = ruta if os.path.exists(ruta) else next(v for v, n in renombres.items() if n == archivo)
        real = real if os.path.isabs(real) else os.path.join(ARCHIVO, real)
        n = paginas(real)
        texto = os.path.splitext(archivo)[0] + '.txt'
        tiene_txt = os.path.exists(os.path.join(ARCHIVO, texto)) or texto in renombres.values()
        obra = {
            'book': {'title': titulo, 'subtitle': None, 'author': 'Pepi'},
            'tipo': 'pdf',
            'categoria': libro_de(sin_numero(os.path.splitext(archivo)[0])),
            'fecha_creacion': None,
            'notas_internas': 'Creado automáticamente desde Archivo/' + archivo + '.',
            'en_linea': False,
            'pdf': dict({'archivo': archivo, 'totalPaginas': n}, **({'texto': texto} if tiene_txt else {})),
            'partes': [{'id': 'pt-' + slug[:24], 'titulo': titulo, 'paginaDesde': 1, 'paginaHasta': n, 'estado': 'borrador'}],
            'acciones_nuevas': {},
        }
        nuevas.append((slug, obra))
        slugs.add(slug)
        print(f'+ {archivo} → obras/{slug}.json ({n} págs., {obra["categoria"] or "sin libro"}'
              + (', con txt' if tiene_txt else ', sin txt') + ')')
    if args.lista or not nuevas:
        if args.lista:
            print('(prueba: no se tocó nada)')
        if not nuevas:
            print('No hay PDFs nuevos en Archivo/.')
        return
    for slug, obra in nuevas:
        ruta = os.path.join(OBRAS, slug + '.json')
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(obra, f, ensure_ascii=False, indent=2)
            f.write('\n')
        r = subprocess.run([sys.executable, 'generar_obra.py', os.path.join('obras', slug + '.json')], cwd=HERE,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            sys.exit(r.returncode)


if __name__ == '__main__':
    main()
