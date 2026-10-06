#!/usr/bin/env python3
"""
cowork.py — matriz relacional por criterios, a partir de la lectura del Cowork.

Uso (desde sitio/):
    python matriz/cowork.py [--dry-run]

── Dos capas del corpus ──
ARCHIVO: lo anterior, subido entero (los PDFs de sitio/Archivo/ y todo
  datos-lee/txt). Se relaciona entre sí solo como contexto: no genera
  sugerencias (esas relaciones ya están en los logs).
CUERPO ACTUAL: lo que se escribe ahora y se sube por partes (posteos de
  texto en línea, o con categoría "cuerpo"). Cada parte genera sugerencias
  hacia el archivo y hacia partes anteriores del cuerpo.
Los posteos de texto ocultos (versiones viejas) no participan.

── Criterios ──
Cada párrafo de los informes por dimensión (INFORME GENERAL "relectura
calibrada, por dimensiones", INFORME FINAL de cada carpeta) y de las
entradas del GLOSARIO es un criterio: nombre (negrita o primera frase),
dimensión (tema, género, técnica, estilo, figura, recurrencia, firma,
filiación, concepto, lateral…), obras que nombra con sus páginas, y
palabras ancla (lo que cita entre comillas; en palabras largas se tolera
otra terminación). Lo que depende de Cló pesa 0.3 y no sugiere nada.

── Relaciones (relaciones.json) ──
Dos obras nombradas en un mismo criterio suman 1/(obras del criterio − 1)
en esa dimensión; se acumulan. Suman también la reescritura literal
(tramos de 8 palabras compartidos, en escala log) y la secuencia de blogs.
Las menciones de los logs quedan como evidencia ("dice_el_log"), sin peso.

── Versiones ──
Dos textos que comparten más de la mitad (en el archivo), o una parte del
cuerpo que comparte más del 10 % o más de 300 tramos con una obra, se
toman como versiones: no generan sugerencias y se agrupan en familias
(p.ej. "sí teoría": pap, pop, las posiciones, Nadie).

── Sugerencias (propuestas-cowork.json) ──
Siempre desde una parte del cuerpo:
  criterio   una palabra ancla útil (la usan pocas obras del archivo)
             aparece en la parte y en una obra del archivo (o en una que
             el criterio nombra);
  reescritura  tramos literales compartidos que no llegan a versión;
  léxico raro  dos o más palabras que usan ≤3 obras del archivo y
             reaparecen en la parte (neologismos, vocabulario propio).
Como mucho 2 por criterio y 30 por parte. Ninguna es relación hasta que
se acepta en el taller.

── Vigencia (matriz/vigencia.py) ──
Los textos que cambiaron de nombre se leen con su nombre de ahora: «sí
teoría» es el posteo «pop», «dos puntos» es «:», «1021» es 1-0-2-1. Las
relaciones van entre posteos del sitio (a, b) y juntan lo que el Cowork
leyó con nombres distintos; un texto que no vive en ningún posteo
(muerto) no recibe sugerencias ni relaciones, y un PDF oculto cuyo texto
se publicó escrito no es destino (lo es el escrito). Los poemarios quedan
como estaban. De paso escribe matriz/vigencia.json: papelera ociosa y
textos que faltarían subir.
"""
import glob
import hashlib
import html as htmlmod
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

import vigencia

HERE = os.path.dirname(os.path.abspath(__file__))
SITIO = os.path.dirname(HERE)
RAIZ = os.path.dirname(SITIO)
TXT = os.path.join(RAIZ, 'datos-lee', 'txt')
COWORK = os.path.join(RAIZ, 'datos-lee', 'cowork')
OBRAS = os.path.join(SITIO, 'obras')
SALIDA_REL = os.path.join(HERE, 'relaciones.json')
SALIDA_PROP = os.path.join(HERE, 'propuestas-cowork.json')

UMBRAL_VERSION = 0.5          # entre obras del archivo
UMBRAL_VERSION_CUERPO = 0.1   # una parte del cuerpo que sale de una obra (o >300 tramos)
CUERPO_CATEGORIAS = {'carne', 'cuerpo', 'dia', 'cuerpo-actual'}
LIBROS = {'I': 'I · Estudio', 'II': 'II · Labios', 'III': 'III · Luna', 'IV': 'IV · Póstumos', 'V': 'V · No', 'VI': 'VI · 0'}
TEJA = 8
PESOS = {'reescritura': 0.45, 'mencion': 0.25, 'motivo': 0.2, 'secuencia': 0.1}
# Términos que la corrección del autor (banner del GLOSARIO, 2026-09-16)
# atribuye a Cló: resúmenes de un Claude anterior, no posiciones de Pepi.
# Solo estos: que un párrafo MENCIONE Cló no lo vuelve de Cló (indiferir,
# mismidad, al-menos-dos, +0… son de Pepi aunque nombren a Cló de pasada).
# "+0" sí es de Pepi ("no teoría"); "+0F" no.
CLO = {'epsilon', 'coagulacion', 'g1-g5', 'ax.1-ax.7', 'k1-k3', '+0f'}


def ancla_de_clo(a):
    """Un ancla que es vocabulario de Cló (también en otra forma: coagulan)."""
    a = sin_tildes(a.lower())
    return a in CLO or any(a.startswith(c[:6]) for c in CLO if len(c) >= 6)


def es_de_clo(nombre):
    """La entrada entera es de Cló si TODAS las variantes de su nombre lo son
    ("Ax.1-Ax.7 / K1-K3" sí; "cero positivo / +0 / +0F" no)."""
    variantes = [sin_tildes(v.strip().strip('"“”').lower()) for v in re.split(r'\s*/\s*', re.sub(r'\([^)]*\)', '', nombre)) if v.strip()]
    return bool(variantes) and all(any(v == c or v.startswith(c + ' ') for c in CLO) for v in variantes)
FIN_FRASE = re.compile(r'(?<!\bp)(?<!\bpp)(?<!\bcf)\.\s+(?=[\w"(=*])')
PENDIENTE = re.compile(r'pendiente|revisar si|a[uú]n no|queda por', re.I)
DECLARADA = re.compile(r'identic|literal|compart|reescrib|reescritura|reutiliz|recort|cita |citad|retoma|mismo bloque|anexo|funde|copia', re.I)


def sin_tildes(s):
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', sin_tildes(s.lower())).strip('-')


def limpio(nombre):
    """"05 - V bardo (docx)" → "bardo"; "I- no teoría" → "no teoría"."""
    n = re.sub(r'\.(docx|pdf|txt|log)$', '', nombre.strip(), flags=re.I)
    n = re.sub(r'\.(docx|pdf)$', '', n, flags=re.I)
    n = re.sub(r'\s*\([^)]*\)\s*$', '', n)
    n = re.sub(r'^\s*[0-9]+[ab]?\s*-\s*', '', n)
    n = re.sub(r'^\s*[IVX]+\s*-?\s+', '', n) if re.match(r'^\s*[IVX]+\s*-', n) else re.sub(r'^(I|II|III|IV|V|VI|VII)\s+(?=\S)', '', n)
    return n.strip().rstrip('_').strip()


def palabras(texto):
    """Pares (normalizada, original) de cada palabra."""
    return [(sin_tildes(m.group(0).lower()), m.group(0)) for m in re.finditer(r"[\wñÑ]+(?:['’][\w]+)?", texto)]


# ───────── Obras: corpus de LeE (txt) + sitio ─────────

def cargar_corpus():
    obras = {}
    for ruta in sorted(glob.glob(os.path.join(TXT, '*-txt', '*.txt'))):
        romano = os.path.basename(os.path.dirname(ruta)).split('-')[0]
        titulo = limpio(os.path.basename(ruta))
        oid = slugify(titulo)
        with open(ruta, encoding='utf-8', errors='replace') as f:
            crudo = f.read()
        partes = re.split(r'<<<PAGE (\d+)>>>', crudo)
        paginas = {}
        if len(partes) > 1:
            for i in range(1, len(partes), 2):
                paginas[int(partes[i])] = partes[i + 1]
        else:
            paginas[1] = crudo
        obras[oid] = {'id': oid, 'titulo': titulo, 'libro': LIBROS.get(romano), 'paginas': paginas, 'rol': 'archivo',
                      'txt': os.path.relpath(ruta, RAIZ)}
    return obras


def texto_plano(html):
    """Texto de un capítulo: sin etiquetas ni los restos que deja pegar
    desde Word (<style>, comentarios condicionales, <xml>)."""
    html = re.sub(r'(?is)<(style|script|xml)\b.*?</\1>|<!--.*?-->', ' ', html)
    # entidades (&nbsp;, &amp;…): si no, «nbsp» quedaba como palabra en las citas
    return htmlmod.unescape(re.sub(r'<[^>]+>', ' ', html)).replace('\xa0', ' ')


def rol_de_posteo(o, hay_carne):
    """Posteo de texto: "cuerpo" (lo que se escribe ahora, por partes) si
    tiene la categoría "carne" (o cuerpo/día). Mientras ningún posteo la
    tenga, cuenta como cuerpo todo posteo de texto en línea. El resto es
    "borrador" (versiones viejas ocultas: no generan nada)."""
    if slugify(o.get('categoria') or '') in CUERPO_CATEGORIAS:
        return 'cuerpo'
    return 'cuerpo' if (o.get('en_linea') and not hay_carne) else 'borrador'


def cargar_sitio(obras):
    """Obras del sitio: PDFs (se enlazan al corpus) y posteos de texto."""
    sitio = {}
    hay_carne = False
    for ruta in glob.glob(os.path.join(OBRAS, '*.json')):
        try:
            with open(ruta, encoding='utf-8') as f:
                if slugify(json.load(f).get('categoria') or '') in CUERPO_CATEGORIAS:
                    hay_carne = True
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    for ruta in sorted(glob.glob(os.path.join(OBRAS, '*.json'))):
        if ruta.endswith('-citas.json'):
            continue
        slug = os.path.splitext(os.path.basename(ruta))[0]
        try:
            with open(ruta, encoding='utf-8') as f:
                o = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        titulo = (o.get('book') or {}).get('title') or slug
        if o.get('tipo') == 'pdf':
            archivo = (o.get('pdf') or {}).get('archivo') or ''
            oid = slugify(limpio(archivo))
            # Si hay dos posteos del mismo PDF, manda el que está en línea.
            if oid in obras and (not obras[oid].get('sitio') or o.get('en_linea')):
                obras[oid]['sitio'] = slug
                obras[oid]['rol'] = 'archivo'
            sitio[slug] = {'titulo': titulo, 'tipo_nodo': 'pdf', 'publicado': bool(o.get('en_linea')), 'obra': oid, 'rol': 'archivo'}
        else:
            caps = [c for c in (o.get('chapters') or []) if (c.get('body') or '').strip()]
            if not caps:
                continue
            oid = 'sitio:' + slug
            rol = rol_de_posteo(o, hay_carne)
            obras[oid] = {'id': oid, 'titulo': titulo, 'libro': o.get('categoria'), 'sitio': slug, 'posteo': True, 'rol': rol,
                          'fecha': o.get('fecha_creacion') or '',
                          'paginas': {i + 1: texto_plano(c.get('body') or '') for i, c in enumerate(caps)},
                          'capitulos': {i + 1: c.get('title') or c.get('id') for i, c in enumerate(caps)}}
            sitio[slug] = {'titulo': titulo, 'tipo_nodo': 'post', 'publicado': bool(o.get('en_linea')), 'obra': oid, 'rol': rol}
    return sitio


# ───────── 1. Reescritura ─────────

def reescritura(obras):
    tokens = {}
    frec = Counter()
    for oid, o in obras.items():
        for pag, texto in o['paginas'].items():
            ps = palabras(texto)
            if len(ps) < 20:
                continue
            tokens[(oid, pag)] = ps
            norm = [p[0] for p in ps]
            vistas = {hash(' '.join(norm[i:i + TEJA])) for i in range(len(norm) - TEJA + 1)}
            frec.update(vistas)
    utiles = {h for h, n in frec.items() if 2 <= n <= 8}
    donde = defaultdict(list)
    for clave, ps in tokens.items():
        norm = [p[0] for p in ps]
        for i in range(len(norm) - TEJA + 1):
            h = hash(' '.join(norm[i:i + TEJA]))
            if h in utiles:
                donde[h].append((clave, i))
    pares = defaultdict(lambda: {'n': 0, 'pos': None})
    for h, lugares in donde.items():
        vistos = {}
        for clave, i in lugares:
            vistos.setdefault(clave, i)
        if len({c[0] for c in vistos}) > 4 or len(vistos) < 2:
            continue
        claves = sorted(vistos)
        for a in range(len(claves)):
            for b in range(a + 1, len(claves)):
                ka, kb = claves[a], claves[b]
                if ka[0] == kb[0]:
                    continue
                par = pares[(ka, kb)]
                par['n'] += 1
                if par['pos'] is None:
                    par['pos'] = (vistos[ka], vistos[kb])
    # bloques por par de obras
    por_obra = defaultdict(list)
    for (ka, kb), v in pares.items():
        if v['n'] >= 3:
            por_obra[(ka[0], kb[0])].append((ka[1], kb[1], v['n'], v['pos']))
    bloques = {}
    for (oa, ob), lista in por_obra.items():
        lista.sort()
        grupos = []
        for pa, pb, n, pos in lista:
            g = grupos[-1] if grupos else None
            if g and 0 <= pa - g['a'][1] <= 2 and abs(pb - g['b'][1]) <= 3:
                g['a'][1] = pa
                g['b'][0], g['b'][1] = min(g['b'][0], pb), max(g['b'][1], pb)
                g['n'] += n
                g['pares'].append((pa, pb, n, pos))
            else:
                grupos.append({'a': [pa, pa], 'b': [pb, pb], 'n': n, 'pares': [(pa, pb, n, pos)]})
        bloques[(oa, ob)] = grupos
    return bloques, tokens


def cita(tokens, clave, desde, largo=26):
    ps = tokens.get(clave) or []
    ini = max(0, desde - 4)
    trozo = ' '.join(p[1] for p in ps[ini:ini + largo])
    return ('… ' if ini else '') + trozo + (' …' if ini + largo < len(ps) else '')


# ───────── 2. Menciones en logs ─────────

def obra_de_log(nombre, obras):
    base = re.sub(r'\.log$', '', nombre)
    ids = []
    for trozo in re.split(r'\s\+\s', re.sub(r'^[0-9]+(?:-[0-9]+)?[ab]?\s*-\s*', '', base)):
        t = limpio(trozo)
        oid = slugify(t)
        if oid in obras:
            ids.append(oid)
        else:
            cand = [k for k in obras if k.startswith(oid) or oid.startswith(k)]
            ids += cand[:1]
    return ids


def menciones(obras):
    patrones = {}
    for oid, o in obras.items():
        if o.get('posteo'):
            continue
        t = re.escape(sin_tildes(o['titulo'].lower()))
        patrones[oid] = re.compile(r'"(?:[ivx0-9]+\s*-\s*)?' + t + r'(?:\.docx)?(?:\.pdf|\.txt)?"|(?:[ivx0-9]+\s*-\s*)?\b' + t + r'\.(?:pdf|txt)\b')
    rel = defaultdict(lambda: {'n': 0, 'declarada': 0, 'frases': []})
    logs = sorted(glob.glob(os.path.join(COWORK, 'logs', '*', '*.log')))
    for ruta in logs:
        origenes = obra_de_log(os.path.basename(ruta), obras)
        if not origenes:
            continue
        for oid in origenes:
            obras[oid]['log'] = os.path.relpath(ruta, RAIZ)
        with open(ruta, encoding='utf-8', errors='replace') as f:
            texto = f.read()
        plano = sin_tildes(texto.lower())
        plano = re.sub(r'[“”«»„]', '"', plano)
        for destino, pat in patrones.items():
            if destino in origenes:
                continue
            for m in pat.finditer(plano):
                # Fin de frase: punto y espacio, salvo "p. 3" / "pp. 5-7".
                cortes = [x.end() for x in FIN_FRASE.finditer(plano, max(0, m.start() - 320), m.start())]
                ini = max(cortes + [plano.rfind('\n\n', 0, m.start()) + 2, m.start() - 320, 0])
                sig = FIN_FRASE.search(plano, m.end())
                fin = min([x for x in (sig.end() if sig else -1, plano.find('\n\n', m.end())) if x > 0] + [m.end() + 320])
                frase = re.sub(r'\s+', ' ', texto[ini:fin]).strip().lstrip('.;:,)] ').strip()
                if PENDIENTE.search(frase):
                    continue
                for o in origenes:
                    r = rel[(o, destino)]
                    r['n'] += 1
                    if DECLARADA.search(frase):
                        r['declarada'] += 1
                    if len(r['frases']) < 3 and frase not in r['frases']:
                        r['frases'].append(frase[:420])
    return rel


# ───────── 3. Criterios (informes por dimensión + glosario) ─────────

DIMENSIONES = [(r'tema', 'tema'), (r'usos|genero', 'género'), (r'tecnica|procedimiento', 'técnica'), (r'estilo', 'estilo'),
               (r'figura', 'figura'), (r'recurrencia|motivo', 'recurrencia'), (r'seudonimo|firma|colofon', 'firma'),
               (r'filiacion', 'filiación'), (r'dimensiones adicionales|lateral', 'lateral'),
               (r'aparato conceptual|glosario de t', 'concepto'), (r'discute consigo', 'debate interno'),
               (r'reescritura', 'reescritura')]
FUENTES_CRITERIOS = [
    ('informes', 'INFORME GENERAL - Proyecto Completo (relectura calibrada, por dimensiones).md'),
    ('', 'GLOSARIO GENERAL.md'),
]
VACIAS = set('el la los las un una unos unas de del y o a en que se no es por con para su sus lo al como mas más pero sin'.split())


def dimension_de(titulo):
    t = sin_tildes(titulo.lower())
    for pat, d in DIMENSIONES:
        if re.search(pat, t):
            return d
    return None


def fuentes_criterios():
    rutas = [os.path.join(COWORK, *[x for x in par if x]) for par in FUENTES_CRITERIOS]
    rutas += sorted(glob.glob(os.path.join(COWORK, 'logs', '*', 'INFORME FINAL*.md')))
    return [r for r in rutas if os.path.exists(r)]


def titulos_obras(obras):
    """Forma normalizada de cada título → id (para reconocer obras citadas)."""
    t = {}
    for oid, o in obras.items():
        if o.get('posteo'):
            continue
        t[sin_tildes(o['titulo'].lower())] = oid
    return t


def obras_citadas(texto, obras, titulos):
    """Obras nombradas en un párrafo (entre comillas, o títulos largos sin
    comillas) con las páginas que aparecen justo después."""
    plano = re.sub(r'[“”«»]', '"', sin_tildes(texto.lower()))
    halladas = defaultdict(set)
    for t, oid in titulos.items():
        pat = r'"(?:[ivx0-9]+\s*-\s*)?' + re.escape(t) + r'(?:\.docx)?(?:\.pdf)?"'
        if len(t) >= 8 and ' ' in t:
            pat += r'|\b' + re.escape(t) + r'\b'
        for m in re.finditer(pat, plano):
            halladas[oid]
            cola = plano[m.end():m.end() + 45]
            for pm in re.finditer(r'\bpp?\.\s?(\d+)(?:\s?-\s?(\d+))?', cola):
                halladas[oid].add(int(pm.group(1)))
                break
    return halladas


def anclas_de(texto, nombre, titulos):
    """Palabras ancla: lo que el informe cita entre comillas (1 a 5 palabras),
    salvo títulos de obras; más las variantes del nombre en el glosario."""
    anclas = set()
    # Comillas rectas: se emparejan en orden (1ª con 2ª, 3ª con 4ª…), así
    # no se toma lo que queda ENTRE dos citas.
    rectas = [m.start() for m in re.finditer('"', texto)]
    trozos = [texto[rectas[i] + 1:rectas[i + 1]] for i in range(0, len(rectas) - 1, 2)]
    trozos += re.findall(r'[“«]([^”»]{3,48})[”»]', texto)
    for t in trozos:
        if not (3 <= len(t) <= 48) or '\n\n' in t or re.search(r'\bpp?\.\s?\d|[()]', t):
            continue
        a = re.sub(r'\s+', ' ', t).strip(' .,;:')
        n = sin_tildes(a.lower())
        if not (1 <= len(n.split()) <= 5) or len(n) < 4 or n in titulos or re.sub(r'^[ivx0-9]+\s*-\s*', '', n) in titulos:
            continue
        if all(w in VACIAS for w in n.split()) or re.fullmatch(r'[\d\s.,-]+', n):
            continue
        anclas.add(a)
    return anclas


def criterios(obras):
    """Cada párrafo de un informe o del glosario, dentro de una sección de
    dimensión, es un criterio: nombre (su negrita o su primera frase),
    dimensión, obras citadas con páginas y palabras ancla."""
    titulos = titulos_obras(obras)
    lista = []
    for ruta in fuentes_criterios():
        with open(ruta, encoding='utf-8') as f:
            texto = f.read()
        dim, sub = None, None
        for bloque in re.split(r'\n\s*\n', texto):
            b = bloque.strip()
            h = re.match(r'^(#{1,4})\s+(.*)', b)
            if h:
                d = dimension_de(h.group(2))
                if len(h.group(1)) <= 2:
                    dim, sub = d, None
                elif d:
                    dim, sub = d, None
                elif dim:
                    sub = re.sub(r'^\d+(\.\d+)*[a-z]?\s+', '', h.group(2)).strip()
                b = b[h.end():].strip()
                if not b:
                    continue
            if not dim or len(b) < 120:
                continue
            # "*Nota (continuación N…)*" amplía la entrada anterior del
            # glosario: se suma a ella, no es un criterio aparte.
            if ruta.endswith('GLOSARIO GENERAL.md') and re.match(r'^\*Nota\b', b) and lista and lista[-1]['fuente'].endswith('GLOSARIO GENERAL.md'):
                prev = lista[-1]
                for o, pp in obras_citadas(b, obras, titulos).items():
                    prev['obras'][o] = sorted(set(prev['obras'].get(o, [])) | set(pp))
                prev['anclas'] = sorted(set(prev['anclas']) | {a for a in anclas_de(b, prev['nombre'], titulos) if not ancla_de_clo(a)})
                continue
            m = re.match(r'^\*\*(.{3,160}?)\*\*[:.\s—-]*', b)
            nombre = m.group(1).strip().rstrip(':.') if m and not m.group(1).startswith('[') else None
            if not nombre:
                nombre = sub or re.split(r'(?<=[.:;])\s', re.sub(r'[*_#>]', '', b), maxsplit=1)[0][:90]
            nombre = re.sub(r'^[-–•]\s*|^\d+(\.\d+)+\s+|^\d+\.\s+', '', re.sub(r'\s+', ' ', nombre)).strip().rstrip(':')
            citadas = obras_citadas(b, obras, titulos)
            anclas = anclas_de(b, nombre, titulos)
            if ruta.endswith('GLOSARIO GENERAL.md') and m:
                anclas |= {v.strip().strip('"“”') for v in re.split(r'\s*/\s*', re.sub(r'\([^)]*\)', '', m.group(1))) if len(v.strip()) >= 3}
            if not citadas and not anclas:
                continue
            clo = es_de_clo(nombre)
            # en una entrada mixta, lo de Cló no ancla (queda "+0", sale "+0F")
            anclas = {a for a in anclas if not ancla_de_clo(a)}
            lista.append({'id': 'cr-' + hashlib.sha1((os.path.basename(ruta) + nombre).encode()).hexdigest()[:10],
                          'nombre': nombre, 'dimension': dim, 'fuente': os.path.relpath(ruta, RAIZ),
                          'obras': {o: sorted(p) for o, p in citadas.items()}, 'anclas': sorted(anclas), 'clo': clo})
    # Glosario: que una entrada nombre a otra es una remisión, no un ancla
    # (inteligema menciona "absolutos concretos" para pedir que NO se
    # fuerce esa conexión).
    def variantes(n):
        return {sin_tildes(v.strip().strip('"“”').lower()) for v in re.split(r'\s*/\s*', re.sub(r'\([^)]*\)', '', n)) if len(v.strip()) >= 3}
    glos = [c for c in lista if c['fuente'].endswith('GLOSARIO GENERAL.md')]
    for c in glos:
        propias = variantes(c['nombre'])
        ajenas = set().union(*(variantes(o['nombre']) for o in glos if o is not c)) - propias
        c['anclas'] = sorted(a for a in c['anclas'] if sin_tildes(a.lower()) not in ajenas)
    # Un mismo nombre en dos fuentes (informe general y final de carpeta) se une.
    unidos = {}
    for c in lista:
        k = (slugify(c['nombre'])[:60], c['dimension'])
        if k in unidos:
            u = unidos[k]
            for o, p in c['obras'].items():
                u['obras'][o] = sorted(set(u['obras'].get(o, [])) | set(p))
            u['anclas'] = sorted(set(u['anclas']) | set(c['anclas']))
            u['clo'] = u['clo'] or c['clo']
        else:
            unidos[k] = c
    return list(unidos.values())


def patron_ancla(a):
    """La frase ancla, tolerando otra terminación en las palabras largas
    (llamaremos → llamar…, llamado): se fija la raíz y se deja libre el final."""
    partes = []
    for w in a.split():
        w = re.escape(sin_tildes(w.lower()))
        if len(w) >= 7 and w.isalpha():
            partes.append(w[:max(5, len(w) - 3)] + r'\w{0,5}')
        else:
            partes.append(w)
    return re.compile(r'(?<![\w])' + r'\s+'.join(partes) + r'(?![\w])')


# ───────── 4. Secuencia (blogs con fecha) ─────────

def secuencia(obras):
    fechas = {}
    for ruta in glob.glob(os.path.join(COWORK, 'enlaces', '*-dates.md')):
        with open(ruta, encoding='utf-8') as f:
            texto = f.read()
        for bloque in re.split(r'^## ', texto, flags=re.M)[1:]:
            cab = bloque.split('\n', 1)[0]
            m = re.search(r'Rango de fechas detectado: (\d{4}-\d\d-\d\d) -> (\d{4}-\d\d-\d\d)', bloque)
            blog = re.search(r'https?://([^/\s]+)/\d{4}/', bloque)
            oid = slugify(limpio(re.sub(r'\s*\(\d+ pags.*$', '', cab)))
            if m and oid in obras:
                fechas[oid] = {'desde': m.group(1), 'hasta': m.group(2), 'blog': blog.group(1) if blog else None}
    orden = sorted(fechas, key=lambda k: fechas[k]['desde'])
    return fechas, list(zip(orden, orden[1:]))


# ───────── Armado ─────────

def misma_obra(obras, a, b):
    """Texto y PDF de la misma obra (sí teoría / sí teoría (PDF)): no es relación."""
    t = lambda o: slugify(re.sub(r'\s*\(pdf\)\s*$', '', obras[o]['titulo'], flags=re.I))
    return t(a) == t(b)


def norm(valores):
    """Escala logarítmica: un par enorme (Aire ↔ Embriaguez) no aplasta al resto."""
    mx = max(valores.values()) if valores else 0
    return {k: (math.log1p(v) / math.log1p(mx) if mx else 0) for k, v in valores.items()}


def pid(*partes):
    return 'cw-' + hashlib.sha1('|'.join(str(p) for p in partes).encode()).hexdigest()[:12]


def main():
    dry = '--dry-run' in sys.argv
    obras = cargar_corpus()
    sitio = cargar_sitio(obras)
    cuerpo = [o for o in obras.values() if o.get('rol') == 'cuerpo']
    print(f'{sum(1 for o in obras.values() if not o.get("posteo"))} obras de archivo con texto · '
          f'{len(cuerpo)} partes del cuerpo actual · {len(sitio)} obras en el sitio')

    # Nombre de ahora de cada texto (vigencia.py): «vigente» es el posteo
    # del sitio donde vive; None si no vive en ninguno.
    vig = vigencia.calcular()
    for o in obras.values():
        if o.get('posteo'):
            o['vigente'] = (vig['sitios'].get(o['sitio']) or {}).get('vigente')
            o['estado'] = 'vivo' if o['vigente'] == o['sitio'] else 'oculto'
        else:
            v = vig['archivo'].get(o.get('txt')) or {}
            o['estado'], o['vigente'] = v.get('estado', 'muerto'), v.get('vigente')

    def destino_ok(oid):
        """Puede recibir una sugerencia: vive en el sitio con su propio
        posteo (un alias o un muerto no: su texto, si está, es otra parte)."""
        o = obras[oid]
        return bool(o.get('vigente')) and o['estado'] in ('vivo', 'poemario')

    bloques, tokens = reescritura(obras)
    menc = menciones(obras)
    crits = criterios(obras)
    fechas, seq = secuencia(obras)
    par = lambda a, b: tuple(sorted((a, b)))

    # ── Versiones: dos obras que comparten la mayor parte de su texto ──
    tejas_obra = Counter()
    for (oid, _), ps in tokens.items():
        tejas_obra[oid] += max(0, len(ps) - TEJA + 1)
    versiones = []
    for (oa, ob), grupos in list(bloques.items()):
        comp = sum(g['n'] for g in grupos)
        menor = min(tejas_obra[oa] or 1, tejas_obra[ob] or 1)
        con_cuerpo = 'cuerpo' in (obras[oa].get('rol'), obras[ob].get('rol'))
        es_version = comp / menor > (UMBRAL_VERSION_CUERPO if con_cuerpo else UMBRAL_VERSION) or (con_cuerpo and comp > 300)
        if misma_obra(obras, oa, ob) or es_version:
            versiones.append({'a': oa, 'b': ob, 'compartido': round(min(1.0, comp / menor), 3)})
            del bloques[(oa, ob)]
    for clave in [k for k in menc if misma_obra(obras, *k)]:
        del menc[clave]

    # ── Anclas: frecuencia en el corpus (cuántas obras las usan) ──
    archivo_ids = [o for o in obras if obras[o].get('rol') == 'archivo']
    planos = {(oid, pag): sin_tildes(t.lower()) for oid, o in obras.items() for pag, t in o['paginas'].items()}
    anclas = {}
    for c in crits:
        for a in c['anclas']:
            if a in anclas or re.search(r'\.(log|md|pdf|docx|txt)$', a, re.I):
                continue
            pat = patron_ancla(a)
            donde = defaultdict(list)
            for (oid, pag), t in planos.items():
                m = pat.search(t)
                if m:
                    donde[oid].append((pag, m.start()))
            n_arch = sum(1 for o in donde if obras[o].get('rol') == 'archivo')
            anclas[a] = {'pat': pat, 'donde': donde, 'n': n_arch}
    n_archivo = max(1, len(archivo_ids))
    # Útil: la usan pocas obras del archivo (no es lengua común del corpus).
    util = {a: v for a, v in anclas.items() if v['n'] <= max(3, n_archivo * 0.15)}
    idf = {a: math.log((n_archivo + 1) / (v['n'] + 1)) + 0.5 for a, v in util.items()}

    # ── Relaciones del archivo (contexto, sin sugerencias entre ellas) ──
    dims = defaultdict(lambda: defaultdict(float))
    evid = defaultdict(lambda: defaultdict(list))
    for c in crits:
        ids = [o for o in c['obras'] if o in obras]
        if len(ids) < 2:
            continue
        w = (0.3 if c['clo'] else 1.0) / (len(ids) - 1)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                k = par(ids[i], ids[j])
                dims[k][c['dimension']] += w
                evid[k]['criterios'].append({'criterio': c['nombre'], 'dimension': c['dimension'], 'fuente': c['fuente'],
                                             'paginas': {ids[i]: c['obras'][ids[i]], ids[j]: c['obras'][ids[j]]},
                                             **({'contexto_amplio': True} if c['clo'] else {})})
    for (oa, ob), grupos in bloques.items():
        k = par(oa, ob)
        dims[k]['reescritura'] += math.log1p(sum(g['n'] for g in grupos)) / 4
        for g in sorted(grupos, key=lambda g: -g['n'])[:4]:
            evid[k]['reescritura'].append({oa: g['a'], ob: g['b'], 'tejas': g['n']})
    for (oa, ob), r in menc.items():
        evid[par(oa, ob)]['dice_el_log'].append({'log_de': oa, 'frases': r['frases']})
    for a, b in seq:
        dims[par(a, b)]['secuencia'] += 0.5
        evid[par(a, b)]['secuencia'].append({'antes': a, 'despues': b})
    # Las relaciones van entre posteos del sitio (vigentes): lo que el
    # Cowork leyó con dos nombres («sí teoría» y su PDF, «pop») se junta;
    # lo que toca un texto muerto, o queda dentro de un mismo posteo, no va.
    juntas = {}
    hacia_muertos = Counter()
    for k in set(dims) | set(evid):
        va, vb = obras[k[0]].get('vigente'), obras[k[1]].get('vigente')
        if not va or not vb:
            for x in k:
                if not obras[x].get('vigente'):
                    hacia_muertos[obras[x]['titulo']] += 1
            continue
        if va == vb:
            continue
        kv = tuple(sorted((va, vb)))
        j = juntas.setdefault(kv, {'dims': defaultdict(float), 'evid': defaultdict(list), 'cowork': []})
        for x, v in dims[k].items():
            j['dims'][x] += v
        for x, v in evid[k].items():
            j['evid'][x].extend(v)
        j['cowork'].append(list(k))
    relaciones = []
    for (a, b), j in juntas.items():
        d = {x: round(v, 3) for x, v in j['dims'].items() if v}
        relaciones.append({'a': a, 'b': b, 'peso': round(sum(d.values()), 3), 'dimensiones': d,
                           'n_criterios': len(j['evid'].get('criterios', [])), 'obras_cowork': sorted(j['cowork']),
                           'evidencia': dict(j['evid'])})
    relaciones.sort(key=lambda r: (-r['peso'], r['a'], r['b']))

    # ── Sugerencias: del cuerpo actual hacia el archivo (y partes anteriores) ──
    def lado(oid, pag, desde):
        o = obras[oid]
        d = {'sitio': o.get('vigente') or o['sitio'], 'cita': cita(tokens, (oid, pag), desde)}
        if o.get('posteo'):
            d['capitulo'] = o['capitulos'].get(pag)
            d['pdf_pagina'] = None
        else:
            d['pdf_pagina'] = pag
        return d

    def indice_palabra(oid, pag, pos_char):
        return len(palabras(obras[oid]['paginas'][pag][:0])) if pos_char is None else \
            len(re.findall(r"[\wñÑ]+(?:['’][\w]+)?", sin_tildes(obras[oid]['paginas'][pag].lower())[:pos_char]))

    version_de = {frozenset((v['a'], v['b'])) for v in versiones}
    propuestas = []
    for c in crits:
        if c['clo']:
            continue
        for a in c['anclas']:
            if a not in util:
                continue
            donde = util[a]['donde']
            origenes = [o for o in donde if obras[o].get('rol') == 'cuerpo']
            destinos = [o for o in donde if destino_ok(o) and obras[o].get('rol') == 'archivo']
            # también las obras que el criterio nombra, aunque la palabra no esté en su texto
            destinos += [o for o in c['obras'] if o in obras and destino_ok(o) and obras[o].get('rol') == 'archivo' and o not in destinos]
            for oa in origenes:
                pa, posa = donde[oa][0]
                for ob in destinos + [x for x in origenes if x != oa and destino_ok(x) and obras[x]['fecha'] <= obras[oa]['fecha']]:
                    if frozenset((oa, ob)) in version_de:
                        continue
                    if ob in donde:
                        pb, posb = donde[ob][0]
                    elif c['obras'].get(ob):
                        pb, posb = c['obras'][ob][0], None
                        if (ob, pb) not in tokens:
                            continue
                    else:
                        continue
                    hacia = 'el archivo' if obras[ob].get('rol') == 'archivo' else 'una parte anterior del cuerpo'
                    propuestas.append({
                        'id': pid('criterio', c['id'], a, oa, pa, ob, pb), 'tipo': c['dimension'], 'instrumento': None,
                        'estatuto': 'lectura-cowork', 'backend': 'cowork',
                        'tipo_relacion': c['dimension'] + ': ' + c['nombre'][:70],
                        'origen': lado(oa, pa, indice_palabra(oa, pa, posa)),
                        'destino': lado(ob, pb, indice_palabra(ob, pb, posb) if posb is not None else 0),
                        'puntaje': {'total': round(min(1.0, idf[a] / (math.log(n_archivo + 1) + 0.5)), 4)},
                        'explicacion': {'por_que': f'Criterio «{c["nombre"]}» ({c["dimension"]}, {os.path.basename(c["fuente"])}): '
                                                   f'«{a}» aparece en esta parte y en {hacia}'
                                                   + (f' («{obras[ob]["titulo"]}», que el informe nombra en este criterio)' if ob in c['obras'] else f' («{obras[ob]["titulo"]}»)') + '.',
                                        'semillas': [a]}})
    for (oa, ob), grupos in bloques.items():
        for x, y in ((oa, ob), (ob, oa)):
            if obras[x].get('rol') != 'cuerpo' or not destino_ok(y) or obras[y].get('rol') not in ('archivo', 'cuerpo'):
                continue
            for g in sorted(grupos, key=lambda g: -g['n'])[:2]:
                pa, pb, n, pos = max(g['pares'], key=lambda t: t[2])
                px, py, posx, posy = (pa, pb, pos[0], pos[1]) if x == oa else (pb, pa, pos[1], pos[0])
                propuestas.append({
                    'id': pid('reescritura', x, px, y, py), 'tipo': 'reescritura', 'instrumento': None,
                    'estatuto': 'lectura-cowork', 'backend': 'cowork', 'tipo_relacion': 'reescritura',
                    'origen': lado(x, px, posx), 'destino': lado(y, py, posy),
                    'puntaje': {'total': round(min(1.0, math.log1p(g['n']) / 6), 4), 'tejas': g['n']},
                    'explicacion': {'por_que': f'Tramo literal compartido: {g["n"]} tramos de 8 palabras entre esta parte y «{obras[y]["titulo"]}».', 'semillas': []}})

    # ── Léxico raro compartido: palabras que usan pocas obras del archivo
    # (≤3) y reaparecen en una parte del cuerpo. Pesa poco; sirve como
    # "parecido en algo" cuando no hay criterio ni tramo literal. ──
    en_obras = defaultdict(set)
    paginas_de = defaultdict(lambda: defaultdict(int))
    for (oid, pag), ps in tokens.items():
        if obras[oid].get('rol') != 'archivo':
            continue
        for w, _ in ps:
            if len(w) >= 6 and not w.isdigit():
                en_obras[w].add(oid)
                paginas_de[w][(oid, pag)] += 1
    raras = {w for w, os_ in en_obras.items() if len(os_) <= 3 and sum(paginas_de[w].values()) >= 2}
    for oa in [o for o in obras if obras[o].get('rol') == 'cuerpo']:
        for pa in sorted(obras[oa]['paginas']):
            ps = tokens.get((oa, pa)) or []
            comunes = defaultdict(set)
            for w, _ in ps:
                if w in raras:
                    for (ob, pb), n in paginas_de[w].items():
                        if destino_ok(ob) and frozenset((oa, ob)) not in version_de:
                            comunes[(ob, pb)].add(w)
            for (ob, pb), ws in sorted(comunes.items(), key=lambda kv: -len(kv[1]))[:3]:
                if len(ws) < 2:
                    continue
                w0 = sorted(ws)[0]
                ia = next((i for i, (w, _) in enumerate(ps) if w in ws), 0)
                ib = next((i for i, (w, _) in enumerate(tokens.get((ob, pb)) or []) if w in ws), 0)
                originales = sorted({o for w, o in ps if w in ws})
                propuestas.append({
                    'id': pid('lexico', oa, pa, ob, pb), 'tipo': 'léxico raro', 'instrumento': None,
                    'estatuto': 'lectura-cowork', 'backend': 'cowork', 'tipo_relacion': 'léxico compartido',
                    'origen': lado(oa, pa, ia), 'destino': lado(ob, pb, ib),
                    'puntaje': {'total': round(min(0.6, 0.12 * len(ws)), 4)},
                    'explicacion': {'por_que': f'Palabras poco frecuentes en el archivo que esta parte comparte con «{obras[ob]["titulo"]}»: '
                                               + ', '.join(originales[:8]) + '.', 'semillas': originales[:8]}})

    # Variedad: por parte, como mucho 2 por criterio y 30 en total.
    vistos, pares_vistos, por_crit, por_parte, finales = set(), set(), Counter(), Counter(), []
    for p in sorted(propuestas, key=lambda p: (-p['puntaje']['total'], p['id'])):
        k_crit = (p['origen']['sitio'], p['tipo_relacion'] if p['tipo'] != 'léxico raro' else 'léxico:' + p['destino']['sitio'])
        k_par = (p['origen']['sitio'], p['origen'].get('pdf_pagina'), p['origen'].get('capitulo'),
                 p['destino']['sitio'], p['destino'].get('pdf_pagina'), p['destino'].get('capitulo'))
        if p['id'] in vistos or k_par in pares_vistos or por_crit[k_crit] >= 2 or por_parte[p['origen']['sitio']] >= 30:
            continue
        pares_vistos.add(k_par)
        vistos.add(p['id'])
        por_crit[k_crit] += 1
        por_parte[p['origen']['sitio']] += 1
        finales.append(p)
    propuestas = finales

    # Familias: las versiones se agrupan (componentes conexas) y toman el
    # nombre de su obra del archivo más larga ("sí teoría": pap, pop…).
    madre = {}
    def raiz(x):
        while madre.get(x, x) != x:
            x = madre[x]
        return x
    for v in versiones:
        if 'borrador' in (obras[v['a']].get('rol'), obras[v['b']].get('rol')):
            continue
        madre[raiz(v['a'])] = raiz(v['b'])
    grupos = defaultdict(set)
    for x in list(madre):
        grupos[raiz(x)].add(x)
        grupos[raiz(x)].add(raiz(x))
    familias = []
    for miembros in grupos.values():
        arch = [m for m in miembros if obras[m].get('rol') == 'archivo'] or list(miembros)
        cabeza = max(arch, key=lambda m: len(obras[m]['paginas']) if obras[m].get('rol') == 'archivo' else 0)
        familias.append({'familia': obras[cabeza]['titulo'],
                         'miembros': sorted(obras[m]['titulo'] for m in miembros if m != cabeza)})
    familias.sort(key=lambda f: f['familia'])

    ahora = datetime.now().isoformat(timespec='seconds')
    salida_rel = {
        'meta': {'generado': ahora, 'estatuto': 'lectura-cowork',
                 'claves': 'a y b son posteos del sitio (el nombre vigente, ver vigencia.py); obras_cowork, los textos '
                           'del Cowork que juntan (claves de «obras»)',
                 'descartadas_hacia_muertos': dict(sorted(hacia_muertos.items())),
                 'fuentes': [os.path.relpath(r, RAIZ) for r in fuentes_criterios()] + ['datos-lee/txt', 'datos-lee/cowork/logs', 'datos-lee/cowork/enlaces'],
                 'nota': 'Matriz por criterios de la lectura del Cowork: cada criterio compartido suma poco; '
                         'se acumulan por dimensión. Lo que depende de Cló pesa 0.3 y no genera sugerencias.'},
        'obras': {oid: {k: o.get(k) for k in ('titulo', 'libro', 'sitio', 'rol', 'log', 'txt', 'estado', 'vigente') if o.get(k)} | {'paginas': len(o['paginas'])}
                  | ({'fechas': fechas[oid]} if oid in fechas else {}) for oid, o in obras.items()},
        'criterios': [{k: v for k, v in c.items()} for c in crits],
        'versiones': versiones,
        'relaciones': relaciones,
    }
    salida_prop = {
        'meta': {'generado': ahora, 'backend': 'cowork', 'estatuto': 'lectura-cowork',
                 'formula': 'ver el encabezado de matriz/cowork.py',
                 'sitios': {s: {k: v for k, v in d.items() if k != 'obra'} for s, d in sitio.items()},
                 'familias': familias},
        'propuestas': propuestas,
    }
    print(f'{len(crits)} criterios ({sum(1 for c in crits if c["clo"])} de Cló) · {len(util)} palabras ancla útiles · '
          f'{len(relaciones)} relaciones · {len(versiones)} versiones · {len(propuestas)} sugerencias '
          f'({dict(Counter(p["tipo"] for p in propuestas))})')
    for r in relaciones[:10]:
        print(f"  {r['peso']:.2f}  {r['a']} ↔ {r['b']}  {r['dimensiones']}")
    if hacia_muertos:
        print('  sin relaciones (no viven en ningún posteo): ' + ', '.join(f'{t} ({n})' for t, n in sorted(hacia_muertos.items())))
    if dry:
        return
    print('✓ matriz/vigencia.json ' + ('actualizado' if vigencia.guardar(vig) else 'sin cambios'))
    escritos = 0
    for ruta, datos in ((SALIDA_REL, salida_rel), (SALIDA_PROP, salida_prop)):
        # Solo se reescribe si cambió algo más que la fecha (la publicación
        # lo corre siempre y no debe dejar commits vacíos de contenido).
        try:
            with open(ruta, encoding='utf-8') as f:
                previo = json.load(f)
            previo['meta'].pop('generado', None)
            nuevo = json.loads(json.dumps(datos))
            nuevo['meta'].pop('generado', None)
            if previo == nuevo:
                continue
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
            f.write('\n')
        escritos += 1
    print(f'✓ matriz/relaciones.json y propuestas-cowork.json {"actualizados" if escritos else "sin cambios"}')


if __name__ == '__main__':
    main()
