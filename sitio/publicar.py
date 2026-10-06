#!/usr/bin/env python3
"""
publicar.py

Arma web/, la carpeta que publica Cloudflare Pages: el sitio que ve un
visitante. Se genera siempre desde sitio/ (nunca se edita a mano).

Qué entra en web/:
- las páginas del sitio (índice) y las de las herramientas de la
  propietaria, que sin su token (acceso.html) vuelven al índice y no
  traen datos: con el token los leen del repo por la API de GitHub;
- SOLO las obras marcadas "mostrar en el sitio web" en el taller
  (campo en_linea de obras/<slug>.json), y de cada una SOLO los
  capítulos o partes en estado "publicada". Una obra marcada sin ningún
  capítulo publicado no aparece.
- corpus.json con esas obras nada más; subgrafo.json reducido a los
  nombres de los instrumentos que usan sus diagonales (sin pesos ni
  nada más de la matriz).
- busqueda.json: el texto plano de esos capítulos, para el buscador del
  índice (los mismos que ya van en las páginas de las obras).

Qué NO entra nunca: los .json fuente de las obras, los borradores,
acciones.json, matriz/, las plantillas, los scripts, datos-lee/ y los
documentos internos. Una diagonal que apunta a algo que no está en
línea se muestra como "destino aún no publicado", sin citar el texto.

Después de armar web/, recalcula los datos de lectura que salen de lo
que quedó en línea (DERIVADOS: partitura, parientes, cadáver exquisito,
términos) y los copia a web/. Antes se corrían a mano y se atrasaban: un
texto nuevo no entraba en el cadáver ni en la partitura. Son
deterministas: si no cambió nada en línea, salen idénticos. Con --salida
a otra carpeta no se recalculan (leen web/), se copian los que hay.

Ojo con los posteos-PDF: el PDF va entero (no se pueden sacar páginas),
aunque solo algunas partes estén publicadas.

Uso (desde sitio/):
    python publicar.py              # escribe ../web/
    python publicar.py --lista      # solo muestra qué se publicaría
    python publicar.py --salida X   # escribe en otra carpeta
    python publicar.py --sin-derivados   # no recalcula los datos de lectura

No hace falta correrlo a mano: lo corre el botón ⚡ publicar (servidor.py
en tu máquina, o el workflow de GitHub desde la web).
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from util import leer  # noqa: E402
import generar_obra as g  # noqa: E402  (mismas funciones que la publicación local)

# Páginas y recursos que se copian tal cual (sin datos de obras).
# Licencia: circula citando la autoría, sin uso comercial ni obras
# derivadas. Va en el índice y en cada obra (no en las herramientas).
LICENCIA_URL = 'https://creativecommons.org/licenses/by-nc-nd/4.0/deed.es'
LICENCIA_HEAD = ('<meta name="author" content="Pepi"><meta name="copyright" content="© Pepi · CC BY-NC-ND 4.0">'
                 '<link rel="license" href="' + LICENCIA_URL + '">')
ICONO_HEAD = '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
# Dirección principal del sitio (con www): la usan el sitemap y la
# etiqueta canonical de cada página, para que los buscadores guarden una
# sola copia de cada una.
SITIO_URL = 'https://www.p314b.space'
LICENCIA_PIE = ('<footer class="p314b-licencia" style="clear:both;margin:48px auto 0;padding:20px 16px 28px;'
                'max-width:720px;text-align:center;font-size:11.5px;line-height:1.5;opacity:.62">'
                '© Pepi · <a rel="license" href="' + LICENCIA_URL + '" style="color:inherit">CC BY-NC-ND 4.0</a>'
                ' — se puede compartir citando la autoría, sin fines comerciales y sin modificar.</footer>')


LICENCIA_PIE_FIJO = ('<footer class="p314b-licencia" style="position:fixed;right:18px;bottom:12px;z-index:30;'
                     'font-size:10px;letter-spacing:.03em;opacity:.5">© Pepi · <a rel="license" href="'
                     + LICENCIA_URL + '" style="color:inherit">CC BY-NC-ND 4.0</a></footer>')


def licenciar(html, fijo=False):
    """fijo: páginas que no scrollean (posteo-PDF): el pie va en una esquina."""
    if 'p314b-licencia' in html:
        return html
    i = html.lower().find('</head>')
    if i >= 0:
        html = html[:i] + LICENCIA_HEAD + html[i:]
    j = html.lower().rfind('</body>')
    pie = LICENCIA_PIE_FIJO if fijo else LICENCIA_PIE
    return html[:j] + pie + html[j:] if j >= 0 else html + pie


PAGINAS = [
    'index.html',
    # estilos de las páginas de obra: salen de las plantillas para que no
    # se repitan en cada obra (generar_obra.py los enlaza con ../)
    'comun.js',
    'obra.css',
    'pdf-post.css',
    'autor.js',
    'publicar.js',
    'pdf-viewer-core.js',
    # La diagonal como objeto propio: su módulo y lo que la autora carga
    # desde la visualización (nodos, concepto, notas, vínculos, anclas).
    'diagonal.js',
    # recorridos de lectura y el rastro del lector (obras y posteos-PDF)
    'recorrido.js',
    'diagonales.json',
    'lemas.json',
    # lemas del diccionario (lemas_auto.py): diagonal.js y la superficie
    # los leen después de lemas.json
    'lemas-auto.json',
    # «resaltar términos» de la lectura (terminos.py arma terminos.json)
    'resaltador.js',
    'terminos.json',
    # otras lecturas (oír mal a propósito, sismógrafo, partitura, huella):
    # el módulo, la rareza de cada palabra (partitura.py) y la homofonía
    'lectura-extra.js',
    'partitura.json',
    'homofonos.json',
    # mareas: textos con horario (mareas.json lo escribe la autora)
    'mareas.js',
    'mareas.json',
    # huella de lectura propia (solo en el navegador de quien lee)
    'huella.html',
    # ayuda para quien llega: qué es el sitio y qué hace cada cosa
    'ayuda.html',
    # contador de visitas: el aviso de cada página y la página de la autora
    'visita.js',
    'visitas.html',
    # comentarios en cualquier parte: el cuadro (lo carga visita.js) y el
    # apartado donde se leen los aprobados (worker/comentarios.js)
    'comentar.js',
    'comentarios.html',
    # parientes y mismizar (parientes.py) y el cadáver exquisito
    # (cadaver.py): con lo que está en línea, los recalcula main()
    # (DERIVADOS) después de armar web/
    'parientes.json',
    'cadaver.html',
    'cadaver.json',
    # el lector como fragmento: el correo al que llegan las frases
    'lector.json',
    'lector-clave.asc',
    # gemelas del cut-up (Aire en la cuerda / De embriaguez y pathos): lo
    # arma a mano matriz/anexo/scripts/cutup.py
    'gemelas.json',
    # experimento «tercero» (Embriaguez | tercero | Aire): la página y sus
    # datos, que arma a mano matriz/anexo/scripts/tercero.py
    'tercero.html',
    'tercero.json',
    # mapa público del corpus: la página; sus datos (mapa.json) los escribe
    # construir() con lo que está en línea
    'mapa.html',
    # Herramientas de la propietaria, solo el "cascarón": sin token de
    # acceso.html vuelven al índice (autor.js); con token leen y escriben
    # los datos directo en el repo, no de acá.
    'acceso.html',
    'uploader-v1.html',
    'matriz.html',
    'matriz-obras.js',
    # superficie relacional del taller: el módulo; su índice
    # (matriz/superficie/) se lee del repo con el token
    'matriz-superficie.js',
    # anexo metodológico de la matriz: solo el cascarón; los datos
    # (matriz/anexo/) se leen del repo con el token, como matriz.html
    'matriz-anexo.html',
    # matriz autónoma: solo el cascarón; matriz/autonoma.json se lee del
    # repo con el token
    'matriz-autonoma.html',
    'formula_helper.html',
    # visor de PDF de las herramientas (el taller enlaza a lector.html?pdf=…)
    'lector.html',
    # ícono de la pestaña (la diagonal azul) y la página para enlaces rotos
    'favicon.svg',
    '404.html',
    # imagen que acompaña el enlace al compartirlo (og:image)
    'vista-previa.png',
]

# Política de contenido: los scripts salen solo del propio sitio. El token
# de la autora vive en el navegador y cualquier script del sitio podría
# leerlo, así que las librerías (pdf.js, d3, KaTeX, baffle) se sirven desde
# vendor/ con su versión fija (vendor/LEEME.md), no desde un CDN. Las
# fuentes también (vendor/fuentes-5.3.0/): sin Google Fonts, el sitio se ve
# igual aunque esa red esté bloqueada. Lo único que se
# habla por red además del sitio es la API de GitHub (token de la autora).
# Nadie puede meter el sitio en un iframe ajeno.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "img-src 'self' data: blob: https:",
    "connect-src 'self' blob: data: https://api.github.com",
    "worker-src 'self' blob:",
    "frame-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
    "upgrade-insecure-requests",
])

CABECERAS = """# Seguridad, en todas las páginas: solo HTTPS (HSTS), sin adivinar tipos,
# sin iframes ajenos, referer mínimo hacia afuera, sin cámara/micrófono/
# ubicación, y la política de contenido de arriba.
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  X-Content-Type-Options: nosniff
  X-Frame-Options: SAMEORIGIN
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()
  Cross-Origin-Opener-Policy: same-origin
  Content-Security-Policy: """ + CSP + """

# El sitio responde con y sin www; la dirección principal es www (para
# los buscadores, una sola copia).
https://p314b.space/*
  Link: <https://www.p314b.space/:splat>; rel="canonical"

# Que el navegador no guarde copias viejas de los datos ni de las páginas
# (taller, índice, scripts: se revalidan en cada visita, sin Shift+R), y
# que los buscadores no indexen las herramientas.
/corpus.json
  Cache-Control: no-cache
/busqueda.json
  Cache-Control: no-cache
/teselas.json
  Cache-Control: no-cache
/diagonales.json
  Cache-Control: no-cache
/obras/*
  Cache-Control: no-cache
/
  Cache-Control: no-cache
/index.html
  Cache-Control: no-cache
/*.js
  Cache-Control: no-cache
/acceso.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/uploader-v1.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/matriz.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/matriz-anexo.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/matriz-autonoma.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/formula_helper.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/lector.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/tercero.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/huella.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/visitas.html
  X-Robots-Tag: noindex, nofollow
  Cache-Control: no-cache
/mareas.json
  Cache-Control: no-cache
"""

# Buscadores: el sitio sí; las herramientas de la autora, no.
ROBOTS = """User-agent: *
Disallow: /acceso.html
Disallow: /uploader-v1.html
Disallow: /matriz.html
Disallow: /matriz-anexo.html
Disallow: /matriz-autonoma.html
Disallow: /formula_helper.html
Disallow: /lector.html
Disallow: /tercero.html
Disallow: /huella.html
Disallow: /visitas.html

Sitemap: https://www.p314b.space/sitemap.xml
"""


def paginas_indexables(salida):
    """Las páginas que los buscadores pueden guardar: las .html de web/ y
    de web/obras/, menos las que robots.txt oculta y la de error. Rutas
    relativas a web/, ordenadas (el índice primero)."""
    ocultas = {l.split(':', 1)[1].strip().lstrip('/') for l in ROBOTS.splitlines() if l.startswith('Disallow:')}
    ocultas.add('404.html')
    rutas = [os.path.basename(f) for f in glob.glob(os.path.join(salida, '*.html'))]
    rutas += ['obras/' + os.path.basename(f) for f in glob.glob(os.path.join(salida, 'obras', '*.html'))]
    rutas = sorted(r for r in rutas if r not in ocultas)
    if 'index.html' in rutas:
        rutas.remove('index.html')
        rutas.insert(0, 'index.html')
    return rutas


def url_publica(ruta):
    """index.html → la raíz; lo demás, su dirección con www."""
    from urllib.parse import quote
    return SITIO_URL + '/' + ('' if ruta == 'index.html' else quote(ruta))


# Portada: la frase de la autora, tal cual, como descripción.
PORTADA_TITULO = 'p314b'
PORTADA_DESCRIPCION = 'la lengua cayó palabra de lengua que calló la lengua en escribir que habla'
# Obras cuyo título es un signo: en el resultado de búsqueda va el nombre
# con que la autora las nombra (el título de la obra no cambia).
TITULO_PARA_BUSCAR = {'obra': 'sí', 'dos-puntos-escrito': 'dos puntos'}
AUTORA = 'Pepi'


def _esc(t):
    return t.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def para_buscadores(html, ruta, datos_corpus):
    """Título, descripción, canonical, vista previa y ficha (JSON-LD) de
    una página indexable, y el texto de las obras escritas dentro de la
    página como <noscript> (en las demás, el texto está en el PDF).
    Lo que la página ya trae, no se pisa. Nada cambia en pantalla."""
    i = html.lower().find('</head>')
    if i < 0:
        return html
    url = url_publica(ruta)
    slug = os.path.basename(ruta)[:-5]
    es_obra = ruta.startswith('obras/')
    o = datos_corpus.get(slug) if es_obra else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    titulo_actual = (m.group(1).strip() if m else '')
    if ruta == 'index.html':
        titulo, desc = PORTADA_TITULO, PORTADA_DESCRIPCION
    elif es_obra:
        nombre = TITULO_PARA_BUSCAR.get(slug) or re.sub(r'\s*[—-]\s*p314b$', '', titulo_actual) or slug
        titulo = nombre + ' — p314b'
        cat = ((o or {}).get('categoria') or '').strip().lower()
        desc = nombre + (', ' + cat if cat else ', texto') + ' de ' + AUTORA + '. Parte del corpus p314b, para leer en diagonal.'
    else:
        titulo, desc = titulo_actual, None
    if m and titulo and titulo != titulo_actual:
        html = html[:m.start()] + '<title>' + _esc(titulo) + '</title>' + html[m.end():]
        i = html.lower().find('</head>')
    extra = ''
    if 'name="description"' not in html and desc:
        extra += '<meta name="description" content="' + _esc(desc) + '">'
    else:
        md = re.search(r'name="description" content="([^"]*)"', html)
        desc = md.group(1) if md else desc
    if 'rel="canonical"' not in html:
        extra += '<link rel="canonical" href="' + url + '">'
    if 'property="og:title"' not in html and titulo:
        extra += ('<meta property="og:site_name" content="p314b"><meta property="og:type" content="' + ('article' if es_obra else 'website') +
                  '"><meta property="og:locale" content="es"><meta property="og:url" content="' + url + '"><meta property="og:title" content="' +
                  _esc(titulo) + '">' + ('<meta property="og:description" content="' + _esc(desc) + '">' if desc else '') +
                  '<meta property="og:image" content="' + SITIO_URL + '/vista-previa.png">'
                  '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
                  '<meta name="twitter:card" content="summary_large_image">')
    if es_obra and 'application/ld+json' not in html:
        ficha = {'@context': 'https://schema.org', '@type': 'CreativeWork', 'name': titulo.replace(' — p314b', ''),
                 'author': {'@type': 'Person', 'name': AUTORA}, 'inLanguage': 'es', 'url': url,
                 'license': LICENCIA_URL, 'isPartOf': {'@type': 'WebSite', 'name': 'p314b', 'url': SITIO_URL + '/'}}
        if o and o.get('categoria'):
            ficha['genre'] = o['categoria']
        extra += '<script type="application/ld+json">' + json.dumps(ficha, ensure_ascii=False).replace('</', '<\\/') + '</script>'
    elif ruta == 'index.html' and 'application/ld+json' not in html:
        ficha = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'p314b', 'url': SITIO_URL + '/',
                 'inLanguage': 'es', 'author': {'@type': 'Person', 'name': AUTORA}}
        extra += '<script type="application/ld+json">' + json.dumps(ficha, ensure_ascii=False) + '</script>'
    html = html[:i] + extra + html[i:]
    # Obras escritas (sin PDF): el texto también en el HTML, para quien no corre JavaScript.
    mc = re.search(r'const CHAPTERS = (\[.*?\]);\n', html, re.S)
    if es_obra and mc and 'const PDF_ARCHIVO' not in html and '<noscript class="texto-obra">' not in html:
        try:
            caps = json.loads(mc.group(1))
        except ValueError:
            caps = []
        cuerpo = ''.join('<section>' + (('<h2>' + _esc(c.get('title') or '') + '</h2>') if len(caps) > 1 else '') + (c.get('body') or '') + '</section>'
                         for c in caps if c.get('estado', 'publicada') == 'publicada')
        marca = '<nav class="chapter-nav"'
        j = html.find(marca)
        if cuerpo and j >= 0:
            html = html[:j] + '<noscript class="texto-obra">' + cuerpo.replace('</noscript', '<\\/noscript') + '</noscript>' + html[j:]
    return html


def obras_en_linea():
    """[(slug, obra_fuente)] de las obras marcadas en_linea, en el orden
    de corpus.json."""
    corpus = leer(os.path.join(HERE, 'corpus.json'), {'obras': []})
    orden = [o.get('id') for o in corpus.get('obras') or []]
    fuentes = {}
    for ruta in glob.glob(os.path.join(HERE, 'obras', '*.json')):
        slug = os.path.splitext(os.path.basename(ruta))[0]
        if slug.endswith('-citas'):
            continue
        data = leer(ruta)
        if isinstance(data, dict) and data.get('en_linea') is True:
            fuentes[slug] = data
    return sorted(fuentes.items(), key=lambda kv: orden.index(kv[0]) if kv[0] in orden else 10**6)


def unidades_publicadas(fuente):
    es_pdf = fuente.get('tipo') == 'pdf'
    unidades = g.normalizar_partes(fuente.get('partes') or []) if es_pdf else g.normalizar_capitulos(fuente.get('chapters') or [])
    return es_pdf, [u for u in unidades if u.get('estado') == 'publicada']


def construir(salida):
    import terminos
    terminos.escribir()  # términos para resaltar, al día con las fuentes
    corpus_sitio = leer(os.path.join(HERE, 'corpus.json'), {'obras': []})
    registro = leer(os.path.join(HERE, 'acciones.json'), {'acciones': {}})
    registro.setdefault('acciones', {})
    subgrafo = leer(os.path.join(HERE, 'subgrafo.json'), {}) or {}
    with open(os.path.join(HERE, 'obra-template.html'), encoding='utf-8') as f:
        plantilla_post = f.read()
    with open(os.path.join(HERE, 'pdf-post-template.html'), encoding='utf-8') as f:
        plantilla_pdf = f.read()

    # 1. Qué va: obras marcadas y sus unidades publicadas.
    elegidas = []
    avisos = []
    for slug, fuente in obras_en_linea():
        es_pdf, unidades = unidades_publicadas(fuente)
        if not unidades:
            avisos.append(f'  · "{slug}" está marcada para la web pero no tiene capítulos "publicada": no se sube.')
            continue
        elegidas.append((slug, fuente, es_pdf, unidades))

    ids_en_linea = {(slug, u['id']) for slug, _, _, us in elegidas for u in us}
    # Registro reducido: solo acciones cuyo origen está en línea. Un destino
    # fuera de esto queda "pendiente" (no se cita su texto).
    registro_web = {'acciones': {
        aid: a for aid, a in registro['acciones'].items()
        if ((a.get('origen') or {}).get('obra'), (a.get('origen') or {}).get('capitulo')) in ids_en_linea
    }}

    # 2. corpus.json de la web: las entradas del sitio, recortadas.
    por_id = {o.get('id'): o for o in corpus_sitio.get('obras') or []}
    corpus_web = {'obras': []}
    for slug, fuente, es_pdf, unidades in elegidas:
        base = dict(por_id.get(slug) or {})
        acc = [a for a in registro_web['acciones'].values() if (a.get('origen') or {}).get('obra') == slug]
        base.update({
            'id': slug,
            'tipo_nodo': 'pdf' if es_pdf else 'post',
            'tipo': fuente.get('tipo', 'libro'),
            'categoria': fuente.get('categoria'),
            'titulo': fuente['book'].get('title'),
            'subtitulo': fuente['book'].get('subtitle'),
            'autor': fuente['book'].get('author', 'Pepi'),
            'fecha_creacion': fuente.get('fecha_creacion') or base.get('fecha_creacion'),
            '_file': slug + '.html',
            '_chapters': [g.resumen_unidad(u, registro_web, slug) for u in unidades],
            '_totalAcciones': len(acc),
            '_totalDiags': sum(1 for a in acc for t in a.get('tipos') or [] if t.get('tipo') == 'diagonal'),
            '_totalWords': sum(len(re.sub(r'<[^>]+>', '', u.get('body') or '').split()) for u in unidades),
            '_estado': 'publicada',
            # Sección del índice y serie: salen de la obra misma.
            'seccion': fuente.get('seccion') or ('pdf' if es_pdf else 'principal'),
            'serie': (fuente.get('serie') or '').strip() or None,
            'serie_orden': fuente.get('serie_orden'),
            # posteo de una diagonal: no va al índice, se llega por la diagonal
            'diagonal': (fuente.get('diagonal') or '').strip() or None,
        })
        if es_pdf:
            # Sin cuerpo: las palabras salen del texto del PDF, solo de las
            # páginas de las partes publicadas (ver generar_obra.palabras_pdf).
            por_pagina = g.palabras_pdf(fuente)
            ultima = max(por_pagina or {1: 0})
            rango = lambda u: range(u.get('paginaDesde') or 1, (u.get('paginaHasta') or ultima) + 1)
            for r, u in zip(base['_chapters'], unidades):
                r['_palabras'] = sum(por_pagina.get(pg, 0) for pg in rango(u))
            base['_totalWords'] = sum(por_pagina.get(pg, 0) for pg in {pg for u in unidades for pg in rango(u)})
        base.pop('_citas_json', None)
        corpus_web['obras'].append(base)

    # 3. Escribir web/ desde cero.
    if os.path.exists(salida):
        shutil.rmtree(salida)
    os.makedirs(os.path.join(salida, 'obras'))
    for rel in PAGINAS:
        src = os.path.join(HERE, rel)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(salida, rel))
    # librerías de terceros, servidas desde el sitio (ver CSP arriba)
    shutil.copytree(os.path.join(HERE, 'vendor'), os.path.join(salida, 'vendor'))
    with open(os.path.join(salida, 'index.html'), encoding='utf-8') as f:
        indice = f.read()
    with open(os.path.join(salida, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(licenciar(indice))
    with open(os.path.join(salida, 'mapa.html'), encoding='utf-8') as f:
        pagina_mapa = f.read()
    with open(os.path.join(salida, 'mapa.html'), 'w', encoding='utf-8') as f:
        f.write(licenciar(pagina_mapa))

    # Archivo/: todos los PDFs y su manifest, así el taller de la web puede
    # elegirlos y armar posteos-PDF (los txt de atrás no se copian).
    pdfs = sorted(f for f in os.listdir(os.path.join(HERE, 'Archivo')) if f.lower().endswith('.pdf')) \
        if os.path.isdir(os.path.join(HERE, 'Archivo')) else []
    os.makedirs(os.path.join(salida, 'Archivo'), exist_ok=True)
    # Láminas: PDF propios de una obra (se abren desde una acción «lámina»).
    # Van a la web, pero no al manifest ni al índice: no son posteos.
    if os.path.isdir(os.path.join(HERE, 'Archivo', 'laminas')):
        shutil.copytree(os.path.join(HERE, 'Archivo', 'laminas'), os.path.join(salida, 'Archivo', 'laminas'))
    for f in pdfs:
        shutil.copy2(os.path.join(HERE, 'Archivo', f), os.path.join(salida, 'Archivo', f))
    with open(os.path.join(salida, 'Archivo', 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(pdfs, f, ensure_ascii=False, indent=2)
        f.write('\n')

    instrumentos_usados = set()
    for slug, fuente, es_pdf, unidades in elegidas:
        corpus_obra = dict(fuente)
        if es_pdf:
            corpus_obra['partes'] = unidades
            html = g.build_pdf_html(corpus_obra, slug, plantilla_pdf, registro_web, corpus_web)
        else:
            corpus_obra['chapters'] = unidades
            html = g.build_obra_html(corpus_obra, slug, plantilla_post, registro_web, corpus_web)
        # Un destino que existe pero no está en línea: "pendiente", no "roto".
        html = licenciar(html.replace('"_roto":true', '"_pendiente":true'), fijo=es_pdf)
        with open(os.path.join(salida, 'obras', slug + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        if es_pdf:
            archivo = (fuente.get('pdf') or {}).get('archivo')
            src = os.path.join(HERE, 'Archivo', archivo or '')
            if not (archivo and os.path.isfile(src)):
                avisos.append(f'  · "{slug}": el PDF {archivo!r} no está en sitio/Archivo/ (hay que subirlo al repo).')
        for a in registro_web['acciones'].values():
            if (a.get('origen') or {}).get('obra') == slug:
                instrumentos_usados.update(t.get('instrumento') for t in a.get('tipos') or [] if t.get('instrumento'))

    # Series: posteos que la autora agrupó (campo "serie", ordenados por
    # "serie_orden") también se publican juntos, como un solo libro, en
    # obras/serie-<nombre>.html. No se duplica nada: se arma de las partes.
    series = {}
    for slug, fuente, es_pdf, unidades in elegidas:
        nombre = (fuente.get('serie') or '').strip()
        if nombre and not es_pdf:
            series.setdefault(nombre, []).append((fuente.get('serie_orden') or 10**6, slug, fuente, unidades))
    for nombre, miembros in series.items():
        if len(miembros) < 2:
            continue
        miembros.sort(key=lambda m: (m[0], m[1]))
        slug_serie = 'serie-' + g.slugify(nombre)
        capitulos = []
        for _, slug, fuente, unidades in miembros:
            for u in unidades:
                u = dict(u)
                u['part'] = u.get('part') or fuente['book'].get('title')
                capitulos.append(u)
        slugs = {m[1] for m in miembros}
        # Las acciones de las partes pasan a ser de la serie: las diagonales
        # entre partes se recorren adentro del libro.
        registro_serie = {'acciones': {
            aid: dict(a, origen=dict(a.get('origen') or {}, obra=slug_serie))
            if (a.get('origen') or {}).get('obra') in slugs else a
            for aid, a in registro_web['acciones'].items()
        }}
        corpus_serie = {'book': {'title': nombre, 'subtitle': None, 'author': 'Pepi'}, 'chapters': capitulos}
        html = licenciar(g.build_obra_html(corpus_serie, slug_serie, plantilla_post, registro_serie, corpus_web)
                         .replace('"_roto":true', '"_pendiente":true'))
        with open(os.path.join(salida, 'obras', slug_serie + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)

    with open(os.path.join(salida, 'corpus.json'), 'w', encoding='utf-8') as f:
        json.dump(corpus_web, f, ensure_ascii=False, indent=2)
        f.write('\n')
    # teselas.json: peso relacional y frases para citar en el mosaico del
    # índice (ver teselas.py). En la web, solo de lo publicado: frases de
    # los capítulos y partes en línea, relaciones entre ellos nada más.
    import teselas
    teselas.escribir()
    with open(os.path.join(salida, 'teselas.json'), 'w', encoding='utf-8') as f:
        json.dump(teselas.armar(elegidas, registro, ids_en_linea), f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    # busqueda.json: el texto plano de cada capítulo publicado, para el
    # buscador del índice. Sin esto, el índice bajaba todas las obras
    # (varios MB) para sacarles el texto. Los posteos-PDF no llevan texto
    # embebido: van vacíos, igual que antes (y así el índice no los baja).
    busqueda = {}
    for slug, fuente, es_pdf, unidades in elegidas:
        busqueda[slug + '.html'] = [] if es_pdf else [
            {'id': u.get('id'), 'titulo': u.get('title') or 'Sin título', 'texto': texto}
            for u in unidades
            for texto in [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', u.get('body') or '')).strip()]
            if texto
        ]
    with open(os.path.join(salida, 'busqueda.json'), 'w', encoding='utf-8') as f:
        json.dump({'obras': busqueda}, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    etiquetas = {i.get('id'): i.get('label') for i in subgrafo.get('instrumentos') or []}
    with open(os.path.join(salida, 'subgrafo.json'), 'w', encoding='utf-8') as f:
        json.dump({'instrumentos': [{'id': i, 'label': etiquetas.get(i) or i} for i in sorted(instrumentos_usados)]},
                  f, ensure_ascii=False, indent=2)
        f.write('\n')
    # mapa.json: el mapa público del corpus (mapa.html). Las obras en línea
    # y las diagonales entre ellas, solo cuando los DOS extremos están
    # publicados (origen y destino en registro_web). Sin textos: lo que se
    # lee está en las obras. Lo que no está en línea no aparece.
    mapa = {'obras': [], 'diagonales': []}
    for o in corpus_web['obras']:
        if o.get('diagonal'):
            continue
        mapa['obras'].append({'id': o['id'], 'titulo': o.get('titulo') or o['id'], 'categoria': o.get('categoria'),
                              'tipo_nodo': o.get('tipo_nodo'), 'archivo': o.get('_file'),
                              'palabras': o.get('_totalWords') or 0})
    en_mapa = {o['id'] for o in mapa['obras']}
    acciones_web = registro_web['acciones']
    for aid, a in sorted(acciones_web.items()):
        de = (a.get('origen') or {}).get('obra')
        for t in a.get('tipos') or []:
            if t.get('tipo') != 'diagonal':
                continue
            destino = acciones_web.get(t.get('destino')) or {}
            hacia = (destino.get('origen') or {}).get('obra')
            if de in en_mapa and hacia in en_mapa:
                mapa['diagonales'].append({
                    'de': de, 'a': hacia, 'accion': aid, 'destino': t.get('destino'),
                    'relacion': t.get('tipo_relacion') or None,
                    'signo': t.get('signo') or None,
                    'instrumento': None if t.get('vacia') else (etiquetas.get(t.get('instrumento')) or t.get('instrumento_nuevo_label') or t.get('instrumento') or None),
                    'vacia': bool(t.get('vacia')) or None,
                })
    # Anclas de diagonal vacías: las relaciones que la autora aceptó en la
    # matriz (matriz/decisiones.json) y que todavía no son una diagonal
    # tendida en el texto. Valen sin emergente. Por par de textos, solo
    # cuando los dos están en línea, con cuántas son y sus tipos de
    # relación: ni citas ni emergentes (eso vive en el taller).
    fijadas = {}
    for d in (leer(os.path.join(HERE, 'matriz', 'decisiones.json'), {}) or {}).get('decisiones') or []:
        if d.get('decision') not in ('aceptada', 'retipada') or d.get('accion'):
            continue
        de, hacia = (d.get('origen') or {}).get('sitio'), (d.get('destino') or {}).get('sitio')
        if de == hacia or de not in en_mapa or hacia not in en_mapa:
            continue
        k = tuple(sorted((de, hacia)))
        par = fijadas.setdefault(k, {'de': k[0], 'a': k[1], 'n': 0, 'relaciones': {}})
        par['n'] += 1
        rel = (d.get('tipo_relacion') or '').strip()
        if rel:
            par['relaciones'][rel] = par['relaciones'].get(rel, 0) + 1
    mapa['fijadas'] = [dict(p, relaciones=[r for r, _ in sorted(p['relaciones'].items(), key=lambda x: (-x[1], x[0]))[:3]])
                       for _, p in sorted(fijadas.items())]
    with open(os.path.join(salida, 'mapa.json'), 'w', encoding='utf-8') as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
        f.write('\n')
    # recorridos.json: los recorridos de matriz/recorridos.json reducidos a
    # lo que está en línea, como una lista de paradas (anclas) para leer en
    # orden desde las obras (?recorrido en el hash). Un paso entra solo si
    # sus dos anclas están publicadas; sin textos, solo ids y títulos.
    recs_web, vistos = [], set()
    for r in (leer(os.path.join(HERE, 'matriz', 'recorridos.json'), {}) or {}).get('recorridos') or []:
        paradas = []
        for p in r.get('pasos') or []:
            de, ha = p.get('desde') or {}, p.get('hacia') or {}
            if de.get('accion') not in acciones_web or ha.get('accion') not in acciones_web:
                continue
            if de.get('sitio') not in en_mapa or ha.get('sitio') not in en_mapa:
                continue
            for ext, diag in ((de, None), (ha, p.get('diagonal'))):
                if paradas and paradas[-1]['accion'] == ext['accion']:
                    continue
                paradas.append({'accion': ext['accion'], 'obra': ext['sitio'], 'titulo': ext.get('titulo') or ext['sitio'],
                                'archivo': ext['sitio'] + '.html', 'diagonal': diag})
        # Recortados a lo publicado, varios recorridos pueden quedar iguales:
        # se muestra uno solo (el primero, en el orden de la matriz).
        firma = tuple(x['accion'] for x in paradas)
        if len(paradas) >= 2 and firma not in vistos:
            vistos.add(firma)
            recs_web.append({'id': r.get('id'), 'etiqueta': r.get('etiqueta') or r.get('id'),
                             'criterio': r.get('criterio'), 'paradas': paradas})
    with open(os.path.join(salida, 'recorridos.json'), 'w', encoding='utf-8') as f:
        json.dump({'recorridos': recs_web}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    # diagonales.json de la web: un concepto solo apunta a su posteo si ese
    # posteo está publicado.
    dg = leer(os.path.join(HERE, 'diagonales.json'), {}) or {}
    publicados = {slug for slug, _, _, _ in elegidas}
    for info in (dg.get('conceptos') or {}).values():
        if info.get('posteo') not in publicados:
            info['posteo'] = None
    with open(os.path.join(salida, 'diagonales.json'), 'w', encoding='utf-8') as f:
        json.dump(dg, f, ensure_ascii=False, indent=1)
        f.write('\n')
    # Voces (Archivo/voces/): el audio de la autora recitando, de una acción
    # «voz de lector». Solo van a la web los que usa alguna página publicada:
    # un audio de un poema todavía en borrador no sale.
    voces = os.path.join(HERE, 'Archivo', 'voces')
    if os.path.isdir(voces):
        usados = set()
        for f in glob.glob(os.path.join(salida, 'obras', '*.html')):
            with open(f, encoding='utf-8') as fh:
                usados.update(re.findall(r'voces/([A-Za-z0-9._-]+)', fh.read()))
        for nombre in sorted(usados):
            origen = os.path.join(voces, nombre)
            if os.path.isfile(origen):
                os.makedirs(os.path.join(salida, 'Archivo', 'voces'), exist_ok=True)
                shutil.copy2(origen, os.path.join(salida, 'Archivo', 'voces', nombre))
    # Ícono de la pestaña en todas las páginas (sin él, el globo genérico).
    for f in glob.glob(os.path.join(salida, '*.html')) + glob.glob(os.path.join(salida, 'obras', '*.html')):
        with open(f, encoding='utf-8') as fh:
            html = fh.read()
        i = html.lower().find('</head>')
        if i < 0 or 'rel="icon"' in html:
            continue
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(html[:i] + ICONO_HEAD + html[i:])
    # Buscadores: cada página indexable dice cuál es su dirección principal
    # (sin ?panel=1, sin la copia sin www), de qué trata y quién la firma;
    # el sitemap las lista todas (abajo).
    indexables = paginas_indexables(salida)
    datos_corpus = {o['id']: o for o in (leer(os.path.join(salida, 'corpus.json'), {}) or {}).get('obras', [])}
    for ruta in indexables:
        f = os.path.join(salida, ruta)
        with open(f, encoding='utf-8') as fh:
            html = fh.read()
        html = para_buscadores(html, ruta, datos_corpus)
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(html)
    with open(os.path.join(salida, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for ruta in indexables:
            f.write('  <url><loc>' + url_publica(ruta) + '</loc></url>\n')
        f.write('</urlset>\n')
    with open(os.path.join(salida, '_headers'), 'w', encoding='utf-8') as f:
        f.write(CABECERAS)
    with open(os.path.join(salida, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(ROBOTS)
    with open(os.path.join(salida, 'LEEME.md'), 'w', encoding='utf-8') as f:
        f.write('# web/\n\nCarpeta generada por `sitio/publicar.py`: es lo que publica Cloudflare Pages.\n'
                'No se edita a mano (se borra y se vuelve a armar en cada publicación).\n')
    return elegidas, avisos


# Datos de lectura que se arman con lo que está en línea (leen web/ o
# web/obras/ por publicados.py) y que publicar copia a web/: el script y
# lo que escribe en sitio/. No va acá lo que necesita la caché de la matriz
# (cutup.py → gemelas.json, tercero.py → tercero.json: experimentos sobre
# dos libros fijos), ni lo que toca datos de la autora (contar_homofonos,
# tercero_demanda).
DERIVADOS = [
    ('partitura.py', 'partitura.json'),
    ('terminos.py', 'terminos.json'),
    ('parientes.py', 'parientes.json'),
    ('cadaver.py', 'cadaver.json'),
]


def recalcular_derivados(salida):
    """Corre cada script de DERIVADOS y copia su salida a web/. Si uno
    falla, queda el .json anterior y se avisa: no frena la publicación."""
    import subprocess
    avisos = []
    for script, archivo in DERIVADOS:
        r = subprocess.run([sys.executable, script], cwd=HERE, capture_output=True, text=True)
        if r.returncode != 0:
            ultima = (r.stderr.strip().splitlines() or ['sin detalle'])[-1]
            avisos.append(f'  · {script} falló ({ultima}): queda el {archivo} anterior')
        if os.path.exists(os.path.join(HERE, archivo)):
            shutil.copy2(os.path.join(HERE, archivo), os.path.join(salida, archivo))
    return avisos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--salida', default=os.path.join(HERE, '..', 'web'))
    ap.add_argument('--lista', action='store_true', help='solo mostrar qué se publicaría')
    ap.add_argument('--sin-derivados', action='store_true', help='no recalcular los datos de lectura (partitura, parientes, cadáver, términos)')
    args = ap.parse_args()

    if args.lista:
        for slug, fuente in obras_en_linea():
            _, us = unidades_publicadas(fuente)
            print(f'{slug}: {len(us)} capítulo(s)/parte(s) publicada(s)')
        return

    salida = os.path.abspath(args.salida)
    elegidas, avisos = construir(salida)
    print(f'✓ web/ armada: {len(elegidas)} obra(s) en línea')
    for slug, _, _, us in elegidas:
        print(f'  · {slug}: {len(us)} capítulo(s)/parte(s)')
    for a in avisos:
        print(a)
    # Los derivados leen web/ (publicados.py): solo si se armó ahí.
    if not args.sin_derivados and os.path.samefile(salida, os.path.join(HERE, '..', 'web')):
        avisos_d = recalcular_derivados(salida)
        print('✓ datos de lectura recalculados: ' + ', '.join(a for _, a in DERIVADOS))
        for a in avisos_d:
            print(a)


if __name__ == '__main__':
    main()
