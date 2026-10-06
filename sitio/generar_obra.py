#!/usr/bin/env python3
"""
generar_obra.py

Convierte un JSON de obra (formato del taller — uploader-v1.html) en
la página de lectura estática (obras/<slug>.html), sincroniza
corpus.json, y funde las acciones (anclas, notas, marginalia, hojear,
diagonales) de esa obra en el registro global sitio/acciones.json.

Uso:
    python3 generar_obra.py mi_obra.json

── Modelo de acciones (reemplaza al diagonals[]/marginalias[]/hojear[]
   embebidos por capítulo de versiones anteriores) ──

La marca vive en el HTML del cuerpo, embebida por el taller al
momento de seleccionar texto y asignarle una acción:

    <span class="accion-mark" data-accion="ac-1a2b3c4">texto</span>

El CONTENIDO de esa acción no vive en el capítulo — vive en
sitio/acciones.json, colección plana, direccionable por id único en
todo el sitio (no por obra, no por capítulo). Un mismo fragmento
visual puede llevar más de un `data-accion` (ids separados por coma)
si tiene más de una acción superpuesta e independiente.

Formato de entrada esperado:
{
  "book": {"title": "no teoría", "subtitle": null, "author": "Pepi"},
  "tipo": "libro",
  "fecha_creacion": "2026-03-01",
  "notas_internas": "",
  "chapters": [
    {
      "id": "ch-c1",                  ← opcional, se genera si falta
      "number": "1", "part": "Primera parte", "title": "C.1",
      "body": "<p>texto con <span class=\"accion-mark\" data-accion=\"ac-xxx\">fragmento</span></p>",
      "estado": "borrador|listo|publicada",   ← default "borrador"
      "pdfName": null
    }
  ],
  "acciones_nuevas": {
    "ac-xxx": {
      "id": "ac-xxx",
      "origen": {"obra": "<slug, lo completa este script si falta>",
                 "capitulo": "ch-c1", "fragmento": "fragmento"},
      "tipos": [
        {"tipo": "ancla"},
        {"tipo": "nota", "contenido": "..."},
        {"tipo": "marginalia", "contenido": "..."},
        {"tipo": "hojear", "destino": "ac-yyy", "cita_relevancia": "..."},
        {"tipo": "diagonal", "destino": "ac-zzz", "emergente": "...",
         "bloque": null, "instrumento": "indiferir_muletilla",
         "instrumento_nuevo_label": null, "reciproca_de": null}
         # instrumento: id de sitio/subgrafo.json (o null). Si la
         # diagonal etiqueta un candidato que todavía no existe ahí,
         # instrumento_nuevo_label trae la etiqueta que tipeó Pepi en
         # el taller — recalcular_subgrafo.py es quien lo da de alta.
      ]
    }
  }
}

`acciones_nuevas` son las acciones creadas o editadas en ESTA sesión
del taller (incluye los stubs recíprocos que el taller genera solo al
crear una diagonal). Este script las funde en el registro global —
no reemplaza el registro entero, actualiza por id.
`acciones_eliminadas` (lista de ids, opcional) son las que se borraron
en el taller: se sacan del registro si son de esta obra.

── Regla de publicación (no negociable) ──
Un capítulo con estado "publicada" no puede tener, entre las acciones
cuyo origen es ese capítulo, ninguna diagonal sin `emergente` o sin
`destino` válido, ni ningún hojear sin `destino` válido. Si las hay,
este script NO escribe nada — ni el HTML, ni corpus.json, ni
acciones.json — y lista los problemas. Es el chequeo que evita
publicar una diagonal a medio atribuir.

── Cita de una diagonal ──
No se guarda texto de cita a mano en la diagonal: como el destino
siempre tiene que ser un id existente y anclado (ya no hay destinos
no-resolubles tipo "canon"/"conversación"), la cita que se muestra en
el ala se deriva en generación del `origen.fragmento` del ID destino.
Si esto no es lo que se quiere, es un cambio de una función — avisar.

── Posteo-PDF (tipo "pdf") ──
Si el JSON trae "tipo": "pdf", se usa pdf-post-template.html en vez de
obra-template.html, y en lugar de "chapters" se leen "partes" (rangos de
página, mismo esquema que partesForExport() del taller) y "pdf": {archivo,
totalPaginas}. Las acciones se anclan a una parte (origen.capitulo) y a una
página (origen.pdf_pagina); la regla de publicación es la misma.

Requiere obra-template.html en la misma carpeta, y corre desde
sitio/, con obras/ como destino:
    sitio/
    ├── generar_obra.py
    ├── obra-template.html
    ├── corpus.json
    ├── acciones.json
    └── obras/
        └── <slug>.html
"""

import glob
import html as html_lib
import json
import re
import os
import sys
from datetime import date

from util import bloque_de, cargar_json, guardar_json, slugify as _slugify

# Windows con consola no-UTF-8 (cp1252/cp437, típico en cmd.exe o
# PowerShell sin chcp 65001): los símbolos que este script imprime
# (✓, ✗, ⚠, ·) tiran UnicodeEncodeError y cortan la corrida. Se fuerza
# UTF-8 en stdout/stderr al arrancar.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, 'obra-template.html')
PDF_TEMPLATE_PATH = os.path.join(HERE, 'pdf-post-template.html')
CORPUS_PATH = os.path.join(HERE, 'corpus.json')
ACCIONES_PATH = os.path.join(HERE, 'acciones.json')
DIAGONALES_PATH = os.path.join(HERE, 'diagonales.json')
OBRAS_DIR = os.path.join(HERE, 'obras')
ARCHIVO_DIR = os.path.join(HERE, 'Archivo')


def esc_html(s):
    return (s or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def uid(prefix='ch-'):
    import random
    import string
    chars = string.ascii_lowercase + string.digits
    return prefix + ''.join(random.choice(chars) for _ in range(7))


def normalizar_capitulos(chapters):
    """Completa 'id' y 'estado' si faltan. Ya no completa diagonals/
    marginalias/hojear — esos arrays quedaron obsoletos, el contenido
    de acción vive en acciones.json, referenciado desde el body."""
    out = []
    for ch in chapters:
        ch = dict(ch)
        ch.setdefault('id', uid())
        ch.setdefault('estado', 'borrador')
        ch.setdefault('_pdfFragment', '')
        out.append(ch)
    return out


def normalizar_partes(partes):
    """Partes de un posteo-PDF (rangos de página), mismo esquema que
    exporta partesForExport() en el taller: {id, titulo, paginaDesde,
    paginaHasta, estado}. Cumplen el rol de los capítulos: las acciones
    se anclan a una parte vía origen.capitulo, y a la página vía
    origen.pdf_pagina."""
    out = []
    for p in partes:
        p = dict(p)
        p.setdefault('id', uid())
        p.setdefault('estado', 'borrador')
        p.setdefault('titulo', '')
        p.setdefault('paginaDesde', 1)
        p.setdefault('paginaHasta', p['paginaDesde'])
        out.append(p)
    return out


def titulo_unidad(u):
    return u.get('title') or u.get('titulo') or ''


def slugify(s):
    return _slugify(s) or 'obra'


def corregir_capitulos(registro, unidades, slug):
    """El capítulo de una acción es donde está su marca en el texto. Si un
    capítulo se fusionó o se rearmó, el dato guardado puede quedar
    apuntando a un id que ya no existe (así «su propio sí» figuraba en
    un capítulo borrado aunque su marca estaba en «Sí y sólo sí»). Acá
    se corrige desde el texto; si la marca no aparece, no se toca."""
    donde = {}
    for u in unidades:
        for grupo in re.findall(r'data-accion="([^"]+)"', u.get('body') or ''):
            for aid in grupo.split(','):
                lista = donde.setdefault(aid.strip(), [])
                if u.get('id') not in lista:
                    lista.append(u.get('id'))
    for aid, accion in registro['acciones'].items():
        origen = accion.get('origen') or {}
        if origen.get('obra') != slug or aid not in donde:
            continue
        # una marca puede cruzar capítulos: solo se corrige si el guardado
        # no tiene la marca en ningún lado
        if origen.get('capitulo') not in donde[aid]:
            print('  · %s: capítulo %s → %s (donde está su marca)' % (aid, origen.get('capitulo'), donde[aid][0]))
            origen['capitulo'] = donde[aid][0]


def fundir_acciones(registro, acciones_nuevas, slug):
    """Funde acciones_nuevas (de esta sesión del taller) en el
    registro global, por id. Completa origen.obra con el slug de esta
    obra si vino vacío (el taller no siempre lo sabe de antemano)."""
    previas = {}
    for aid, accion in (acciones_nuevas or {}).items():
        accion = dict(accion)
        accion.setdefault('id', aid)
        origen = dict(accion.get('origen') or {})
        # Formato viejo del taller: capitulo/fragmento/pdf_pagina en el
        # primer nivel de la acción en vez de dentro de origen.
        for campo in ('capitulo', 'fragmento', 'pdf_pagina'):
            if origen.get(campo) is None and accion.get(campo) is not None:
                origen[campo] = accion.pop(campo)
        origen.setdefault('obra', slug)
        if not origen.get('obra'):
            origen['obra'] = slug
        accion['origen'] = origen
        previas[aid] = registro['acciones'].get(aid) or {}
        registro['acciones'][aid] = accion
    # Las vueltas de diagonales tendidas desde OTRA obra (reciproca_de)
    # viven en el registro, no en el .json de esta: si esta sesión no las
    # trae, se conservan mientras la ida siga apuntando acá.
    for aid, previa in previas.items():
        accion = registro['acciones'][aid]
        tipos = list(accion.get('tipos') or [])
        claves = {(t.get('tipo'), t.get('destino')) for t in tipos}
        for t in previa.get('tipos') or []:
            otra = registro['acciones'].get(t.get('reciproca_de') or '') or {}
            sigue = any(u.get('tipo') == 'diagonal' and u.get('destino') == aid for u in otra.get('tipos') or [])
            if t.get('tipo') == 'diagonal' and sigue and ('diagonal', t.get('destino')) not in claves:
                tipos.append(t)
        accion['tipos'] = tipos
    return registro


def diagonal_con_contenido(t):
    """Una diagonal tiene contenido si tiene emergente (ida o vuelta) o
    algo escrito en los paneles de texto fuente / remitente (editor de
    tres paneles del taller: ninguno es obligatorio por separado). Una
    «ancla de diagonal vacía» (vacia: true) fija la relación sin emergente:
    vale igual."""
    if t.get('vacia'):
        return True
    if (t.get('emergente') or '').strip() or (t.get('emergente_vuelta') or '').strip() or (t.get('resumen') or '').strip():
        return True
    paneles = t.get('paneles') or {}
    for lado in ('fuente', 'remitente'):
        for campo in ('parrafo', 'cita', 'detalle', 'cita_abajo'):
            if ((paneles.get(lado) or {}).get(campo) or '').strip():
                return True
    return False


def acciones_de_capitulo(registro, capitulo_id):
    return {aid: a for aid, a in registro['acciones'].items()
            if (a.get('origen') or {}).get('capitulo') == capitulo_id}


# Un hojear puede apuntar, además de a un id de acción, a una obra entera
# («obra:<slug>») o a una página de una obra PDF («obra:<slug>#p=<n>»): no
# hace falta un ancla del otro lado.
DESTINO_OBRA = re.compile(r'^obra:([a-z0-9-]+)(?:#p=(\d+))?$')


def destino_obra(destino):
    """(slug, página o None) si el destino es una obra; si no, None."""
    m = DESTINO_OBRA.match(destino or '')
    return (m.group(1), int(m.group(2)) if m.group(2) else None) if m else None


def revisar_completitud(chapters, registro):
    """Devuelve lista de strings-error. No negociable: capítulo
    publicada + diagonal/hojear sin destino o sin emergente = error,
    no se genera nada."""
    errores = []
    for ch in chapters:
        if ch.get('estado') != 'publicada':
            continue
        propias = acciones_de_capitulo(registro, ch['id'])
        for aid, accion in propias.items():
            for t in accion.get('tipos') or []:
                tipo = t.get('tipo')
                if tipo == 'diagonal':
                    if not t.get('destino'):
                        errores.append('Cap. "%s" (%s): diagonal %s sin destino.' % (titulo_unidad(ch), ch['id'], aid))
                    # juntas, alcanza con que una de las diagonales tenga emergente
                    juntas = accion.get('diagonales_juntas') and any(
                        x.get('tipo') == 'diagonal' and diagonal_con_contenido(x) for x in accion.get('tipos') or [])
                    if not diagonal_con_contenido(t) and not juntas:
                        errores.append('Cap. "%s" (%s): diagonal %s sin emergente.' % (titulo_unidad(ch), ch['id'], aid))
                    if t.get('destino') and t['destino'] not in registro['acciones']:
                        errores.append('Cap. "%s" (%s): diagonal %s apunta a un ID inexistente (%s).' % (titulo_unidad(ch), ch['id'], aid, t['destino']))
                elif tipo == 'lamina':
                    # PDF propio de la obra (Archivo/laminas/), no un posteo
                    archivo = t.get('archivo') or ''
                    if not re.fullmatch(r'laminas/[A-Za-z0-9][A-Za-z0-9._-]*\.pdf', archivo):
                        errores.append('Cap. "%s" (%s): lámina %s sin PDF.' % (titulo_unidad(ch), ch['id'], aid))
                    elif not os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Archivo', archivo)):
                        errores.append('Cap. "%s" (%s): lámina %s: falta el PDF Archivo/%s.' % (titulo_unidad(ch), ch['id'], aid, archivo))
                elif tipo in ('transclusion', 'tercero'):
                    nombre = 'transclusión' if tipo == 'transclusion' else 'tercero'
                    if not t.get('destino'):
                        errores.append('Cap. "%s" (%s): %s %s sin destino.' % (titulo_unidad(ch), ch['id'], nombre, aid))
                    elif t['destino'] not in registro['acciones']:
                        errores.append('Cap. "%s" (%s): %s %s apunta a un ID inexistente (%s).' % (titulo_unidad(ch), ch['id'], nombre, aid, t['destino']))
                elif tipo == 'hojear':
                    if not t.get('destino'):
                        errores.append('Cap. "%s" (%s): hojear %s sin destino.' % (titulo_unidad(ch), ch['id'], aid))
                    elif t['destino'] not in registro['acciones'] and not destino_obra(t['destino']):
                        errores.append('Cap. "%s" (%s): hojear %s apunta a un ID inexistente (%s).' % (titulo_unidad(ch), ch['id'], aid, t['destino']))
    return errores


def resolver_destino(registro, corpus_data, slug, destino_id, propia=None):
    """Dado un id destino, arma lo que la plantilla necesita para
    mostrar fuente + navegar: si vive en esta misma obra, navegación
    interna (sin archivo); si vive en otra, busca su archivo en
    corpus.json (si esa obra ya fue generada) y arma el link cruzado.
    Nunca falla duro: si no puede resolver, marca _roto.
    propia = (título de esta obra, sus unidades): para que una diagonal
    interna muestre títulos y no el slug / el id del capítulo."""
    a_obra = destino_obra(destino_id)
    if a_obra:
        # hojear hacia una obra entera o una página de una obra PDF
        obra_destino, pagina = a_obra
        misma_obra = obra_destino == slug
        obra_obj = next((o for o in (corpus_data.get('obras') or []) if o.get('id') == obra_destino), None)
        if not misma_obra and not obra_obj:
            return {'_pendiente': True, '_obraDestino': obra_destino}
        titulo_obra = (propia[0] if misma_obra and propia else None) or (obra_obj or {}).get('titulo') or obra_destino
        return {
            'mismaObra': misma_obra,
            'archivo': None if misma_obra else (obra_obj or {}).get('_file'),
            'tituloObra': titulo_obra,
            'tituloCapitulo': titulo_obra + (', pág. %d' % pagina if pagina else ''),
            'fragmento': '',
            'pdf_pagina': pagina,
            'obraEntera': True,
        }
    destino = registro['acciones'].get(destino_id)
    if not destino:
        return {'_roto': True}

    origen = destino.get('origen') or {}
    obra_destino = origen.get('obra')
    capitulo_destino = origen.get('capitulo')
    fragmento_destino = origen.get('fragmento') or ''
    pdf_pagina_destino = origen.get('pdf_pagina')
    misma_obra = (obra_destino == slug)

    archivo = None
    titulo_obra = obra_destino
    titulo_capitulo = capitulo_destino
    if misma_obra and propia:
        titulo_obra = propia[0] or obra_destino
        cap_obj = next((c for c in propia[1] if c.get('id') == capitulo_destino), None)
        if cap_obj:
            titulo_capitulo = titulo_unidad(cap_obj) or capitulo_destino
    if not misma_obra:
        obras = corpus_data.get('obras') or []
        obra_obj = next((o for o in obras if o.get('id') == obra_destino), None)
        if obra_obj:
            archivo = obra_obj.get('_file')
            titulo_obra = obra_obj.get('titulo') or obra_destino
            cap_obj = next((c for c in (obra_obj.get('_chapters') or []) if c.get('id') == capitulo_destino), None)
            if cap_obj:
                titulo_capitulo = titulo_unidad(cap_obj) or capitulo_destino
        else:
            # La obra destino todavía no fue generada — no es error,
            # es un estado transitorio normal mientras se arma el
            # sitio de a partes. Queda marcado para que la plantilla
            # lo muestre como pendiente, no como roto.
            return {'_pendiente': True, '_obraDestino': obra_destino}

    return {
        'mismaObra': misma_obra,
        'archivo': archivo,
        'tituloObra': titulo_obra,
        'tituloCapitulo': titulo_capitulo,
        'fragmento': fragmento_destino,
        'pdf_pagina': pdf_pagina_destino,
    }


def parrafo_de_accion(obra_slug, capitulo_id, accion_id):
    """El párrafo (texto plano) donde está marcada una acción, si su obra
    está en línea y su capítulo publicado; si no, None. Lo usa la
    transclusión: el pasaje de otro lado se muestra entero, y como se
    resuelve en cada publicación, sigue al original si cambia."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    obra = cargar_json(os.path.join(aqui, 'obras', obra_slug + '.json'), None)
    if not obra or obra.get('en_linea') is not True:
        return None
    cap = next((c for c in obra.get('chapters') or [] if c.get('id') == capitulo_id), None)
    if not cap or cap.get('estado') != 'publicada':
        return None
    body = cap.get('body') or ''
    m = re.search(r'data-accion="[^"]*\b%s\b[^"]*"' % re.escape(accion_id), body)
    if not m:
        return None
    trozo = bloque_de(body, m)
    texto = re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', ' ', trozo)))).strip()
    # Un bloque largo (un capítulo entero sin párrafos, un poema con <br>)
    # se recorta alrededor del fragmento: unas 90 palabras.
    if len(texto) > 700:
        frag = re.sub(r'\s+', ' ', html_lib.unescape(re.sub(r'<[^>]+>', '', m.string[m.end():body.find('</span>', m.end())]))).strip()
        i = texto.find(frag) if frag else -1
        if i < 0:
            i = 0
        a, b = max(0, i - 300), min(len(texto), i + len(frag) + 300)
        a = texto.rfind(' ', 0, a) + 1 if a else 0
        b = texto.find(' ', b) if b < len(texto) and texto.find(' ', b) > 0 else len(texto)
        texto = ('… ' if a else '') + texto[a:b] + (' …' if b < len(texto) else '')
    return texto or None


def tipo_publicable(t, registro, corpus_data, slug, propia):
    """Los tipos que la lectura no conoce se publican como uno que sí:
    tercero → hojear (al tercer texto, cuando tercero_demanda.py ya lo
    encontró), lector → marginalia (con firma y fecha). La transclusión
    lleva el párrafo de origen. Devuelve None si todavía no hay nada que
    mostrar."""
    tipo = t.get('tipo')
    if tipo == 'tercero':
        res = t.get('resultado') or {}
        if not res.get('obra'):
            return None
        destino = 'obra:%s' % res['obra'] + ('#p=%d' % res['p'] if res.get('pdf') and res.get('p') else '')
        otro = (registro['acciones'].get(t.get('destino')) or {}).get('origen') or {}
        cita = 'tercero entre este fragmento y «%s»: %s' % ((otro.get('fragmento') or '')[:80], res.get('fragmento') or '')
        h = {'tipo': 'hojear', 'destino': destino, 'cita_relevancia': cita, 'tercero': True}
        h['_resuelto'] = resolver_destino(registro, corpus_data, slug, destino, propia)
        return h
    if tipo == 'lector':
        # audio: la voz recitando (Archivo/voces/), sobre todo para poemas
        # sueltos. Solo con audio y sin frase, no lleva firma de lector.
        audio = t.get('audio') if re.match(r'^voces/[A-Za-z0-9._-]+$', t.get('audio') or '') else None
        frase = (t.get('contenido') or '').strip()
        if audio and not frase and not (t.get('firma') or '').strip():
            pie = ''
        else:
            firma = (t.get('firma') or '').strip() or 'alguien que leyó'
            pie = '— ' + firma + (', ' + t['fecha'] if t.get('fecha') else '')
        m = {'tipo': 'marginalia', 'contenido': frase + ('\n' + pie if pie else '')}
        if pie:
            m['lector'] = True   # solo el audio (la autora): sin «lector ·»
        if audio:
            m['audio'] = audio
        return m
    if tipo == 'transclusion' and t.get('destino'):
        t = dict(t)
        t['_resuelto'] = r = resolver_destino(registro, corpus_data, slug, t['destino'], propia)
        origen = (registro['acciones'].get(t['destino']) or {}).get('origen') or {}
        if not r.get('_roto') and not r.get('_pendiente'):
            r['parrafo'] = parrafo_de_accion(origen.get('obra'), origen.get('capitulo'), t['destino']) or ''
        return t
    return t


def construir_acciones_embebidas(chapters, registro, corpus_data, slug, titulo_obra=None):
    """Subconjunto de acciones.json relevante para ESTA obra: solo
    las que se originan en uno de sus capítulos, con los destinos ya
    resueltos (archivo/título/cita) para que la plantilla no tenga
    que leer acciones.json en vivo."""
    ids_capitulos = {ch['id'] for ch in chapters}
    embebido = {}
    for aid, accion in registro['acciones'].items():
        origen = accion.get('origen') or {}
        if origen.get('obra') != slug or origen.get('capitulo') not in ids_capitulos:
            continue
        tipos_resueltos = []
        for t in accion.get('tipos') or []:
            t = dict(t)
            # #tags: solo del autor, no salen a la página. Un ancla-diagonal
            # se lee como un ancla común.
            t.pop('tags', None)
            if t.get('tipo') == 'ancla-diagonal':
                t = {'tipo': 'ancla'}
            if t.get('tipo') in ('diagonal', 'hojear') and t.get('destino'):
                t['_resuelto'] = resolver_destino(registro, corpus_data, slug, t['destino'], (titulo_obra, chapters))
            t = tipo_publicable(t, registro, corpus_data, slug, (titulo_obra, chapters))
            if t is None:
                continue
            tipos_resueltos.append(t)
        embebido[aid] = {
            'id': aid,
            'capitulo': origen.get('capitulo'),
            'fragmento': origen.get('fragmento'),
            'pdf_pagina': origen.get('pdf_pagina'),
            'tipos': tipos_resueltos,
            # retrolegibilidad: esta acción se abre recién después de haber
            # leído (abierto) la acción "umbral" en la misma visita.
            **({'umbral': accion['umbral']} if accion.get('umbral') else {}),
            # una fuente con varios destinos: una sola tarjeta (todas las
            # citas de destino y un solo emergente) en vez de una por destino
            **({'diagonales_juntas': True} if accion.get('diagonales_juntas') else {}),
        }
    return embebido


def tipo_diagonal(registro, a, b):
    acc = registro['acciones'].get(a) or {}
    return next((t for t in acc.get('tipos') or [] if t.get('tipo') == 'diagonal' and t.get('destino') == b), None)


def datos_posteo_diagonal(concepto, registro, corpus_data):
    """Posteo de una diagonal: las citas de TODAS las diagonales que la
    autora puso bajo este concepto (#dg-…, en diagonales.json), con obra,
    capítulo y orden. Solo se cita lo que está en corpus_data (en la web,
    lo publicado); el otro lado queda vacío."""
    if not concepto:
        return None
    dg = cargar_json(DIAGONALES_PATH, {})
    info = (dg.get('conceptos') or {}).get(concepto) or {}
    obras = {o.get('id'): o for o in corpus_data.get('obras') or []}

    def lado(aid):
        a = registro['acciones'].get(aid)
        if not a:
            return None
        o = a.get('origen') or {}
        ob = obras.get(o.get('obra'))
        if not ob:
            return None
        caps = ob.get('_chapters') or []
        idx = next((i for i, c in enumerate(caps) if c.get('id') == o.get('capitulo')), -1)
        return {'id': aid, 'obra': ob.get('titulo') or o.get('obra'), 'archivo': ob.get('_file'),
                'capitulo': titulo_unidad(caps[idx]) if idx >= 0 else '', 'frag': o.get('fragmento') or '',
                'pdf_pagina': o.get('pdf_pagina'), 'fecha': ob.get('fecha_creacion') or '', 'cap_idx': idx}

    citas = []
    for clave, r in (dg.get('diagonales') or {}).items():
        if (r or {}).get('concepto') != concepto or clave.count('~') != 1:
            continue
        a, b = clave.split('~')
        t, tb = tipo_diagonal(registro, a, b), tipo_diagonal(registro, b, a)
        # sentido original (fuente → destino): el tipo que no es el recíproco
        if t is None or (t.get('reciproca_de') and tb is not None and not tb.get('reciproca_de')):
            a, b, t = b, a, tb
        if t is None:
            continue
        f, d = lado(a), lado(b)
        if not f and not d:
            continue
        citas.append({'clave': clave, 'fuente': f, 'destino': d, 'titulo': t.get('titulo') or '',
                      'relacion': t.get('tipo_relacion') or '', 'instrumento': t.get('instrumento') or '',
                      'instrumento_label': t.get('instrumento_nuevo_label') or '',
                      'instrumento_lema': t.get('instrumento_lema') or ''})
    # de lo anterior a lo posterior: fecha de la obra, lugar en la obra
    citas.sort(key=lambda c: min((x['fecha'], x['cap_idx']) for x in (c['fuente'], c['destino']) if x))
    return {'concepto': concepto, 'nombre': info.get('nombre') or concepto, 'citas': citas}


def sincronizar_posteo_diagonal(corpus, slug):
    """diagonales.json: el concepto cuyo posteo es esta obra apunta a ella
    (y ningún otro concepto la reclama si se la sacó en el taller)."""
    concepto = (corpus.get('diagonal') or '').strip()
    dg = cargar_json(DIAGONALES_PATH, {'conceptos': {}, 'diagonales': {}})
    conceptos = dg.setdefault('conceptos', {})
    cambio = False
    for cid, info in conceptos.items():
        if info.get('posteo') == slug and cid != concepto:
            info['posteo'] = None
            cambio = True
    if concepto:
        info = conceptos.setdefault(concepto, {'nombre': concepto[3:] if concepto.startswith('dg-') else concepto, 'posteo': None})
        if info.get('posteo') != slug:
            info['posteo'] = slug
            cambio = True
    if cambio:
        with open(DIAGONALES_PATH, 'w', encoding='utf-8') as f:
            json.dump(dg, f, ensure_ascii=False, indent=1)
            f.write('\n')
    return concepto if cambio else None


def build_chap_list_html(chapters):
    # ch['number'] es texto libre, editado a mano en el taller, sin valor
    # predefinido: si está vacío no se infiere de la posición ni se le
    # antepone "Cap." — una unidad sin numeración (p.ej. un prólogo)
    # aparece en el índice solo con su título.
    parts = []
    for i, ch in enumerate(chapters):
        active = ' active' if i == 0 else ''
        number = ch.get('number') or ''
        title = ch.get('title') or 'Sin título'
        num_span = ('\n      <span class="num">' + esc_html(str(number)) + '</span>') if number else ''
        parts.append(
            '\n    <a class="index-item' + active + '" data-ch="' + esc_html(str(ch['id'])) + '">' +
            num_span +
            '\n      <span class="name">' + esc_html(str(title)) + '</span>'
            '\n    </a>'
        )
    return ''.join(parts)


def build_obra_html(corpus, slug, template, registro, corpus_data):
    book = corpus['book']
    chapters = corpus['chapters']

    chap_list_html = build_chap_list_html(chapters)
    chapters_data = json.dumps(chapters, ensure_ascii=False, separators=(',', ':'))
    acciones_data = json.dumps(
        construir_acciones_embebidas(chapters, registro, corpus_data, slug, book.get('title')),
        ensure_ascii=False, separators=(',', ':')
    )
    titulo = esc_html(book.get('title'))
    lemas = cargar_json(os.path.join(HERE, 'lemas.json'), {})
    lemas_data = json.dumps({'formas': lemas.get('formas') or {}, 'ignorar': lemas.get('ignorar') or []},
                            ensure_ascii=False, separators=(',', ':'))
    fecha = json.dumps(str(corpus.get('fecha_creacion') or ''))

    out = template
    out = out.replace('___TITULO___', titulo)
    out = out.replace('___CHAPLIST___', chap_list_html)
    out = out.replace('___CHAPTERSDATA___', chapters_data)
    out = out.replace('___ACCIONESDATA___', acciones_data)
    out = out.replace('___LEMASDATA___', lemas_data)
    out = out.replace('___FECHAOBRA___', fecha)
    posteo = datos_posteo_diagonal((corpus.get('diagonal') or '').strip(), registro, corpus_data)
    out = out.replace('___DIAGONALDATA___', json.dumps(posteo, ensure_ascii=False, separators=(',', ':')))
    out = out.replace('___SLUG___', slug)
    return out


def build_pdf_html(corpus, slug, template, registro, corpus_data):
    """Mismos tokens que buildPdfHTML() del taller: la previsualización y
    la publicación tienen que dar el mismo resultado."""
    partes = corpus['partes']
    acciones_data = json.dumps(
        construir_acciones_embebidas(partes, registro, corpus_data, slug, corpus['book'].get('title')),
        ensure_ascii=False, separators=(',', ':')
    )
    out = template
    out = out.replace('___TITULO___', esc_html(corpus['book'].get('title')))
    out = out.replace('___SLUG___', slug)
    out = out.replace('___PDFARCHIVO___', json.dumps((corpus.get('pdf') or {}).get('archivo') or '', ensure_ascii=False))
    out = out.replace('___PARTESDATA___', json.dumps(partes, ensure_ascii=False, separators=(',', ':')))
    out = out.replace('___ACCIONESDATA___', acciones_data)
    return out


def resumen_unidad(u, registro, slug):
    """Capítulo sin cuerpo, con sus palabras y diagonales: el índice muestra
    cada parte de un posteo extenso como un posteo propio."""
    r = {k: v for k, v in u.items() if k != 'body'}
    r['_palabras'] = len(re.sub(r'<[^>]+>', ' ', u.get('body') or '').split())
    r['_diags'] = sum(1 for a in registro['acciones'].values()
                      if (a.get('origen') or {}).get('obra') == slug and (a.get('origen') or {}).get('capitulo') == u.get('id')
                      for t in a.get('tipos') or [] if t.get('tipo') == 'diagonal')
    return r


def palabras_pdf(corpus):
    """Palabras por página de un posteo-PDF (ver texto_pdf). Sin texto, {}
    (cuenta 0)."""
    return {pg: len(t.split()) for pg, t in texto_pdf(corpus).items()}


def texto_pdf(corpus):
    """Texto por página de un posteo-PDF, del texto ya extraído: el .txt
    de Archivo/ (pdf.texto, o el del mismo nombre que el PDF) o, si no
    está, el de datos-lee/txt cuya cabecera nombra ese PDF. Las páginas van
    marcadas «<<<PAGE n>>>». Sin texto, {}."""
    pdf = corpus.get('pdf') or {}
    archivo = pdf.get('archivo') or ''
    aqui = os.path.dirname(os.path.abspath(__file__))
    candidatos = [os.path.join(aqui, 'Archivo', n) for n in
                  (pdf.get('texto'), re.sub(r'\.pdf$', '.txt', archivo, flags=re.I) if archivo else None) if n]
    clave = re.sub(r'[^a-z0-9]+', '', slugify(re.sub(r'\.pdf$', '', archivo, flags=re.I)))
    for f in sorted(glob.glob(os.path.join(os.path.dirname(aqui), 'datos-lee', 'txt', '*', '*.txt'))):
        try:
            with open(f, encoding='utf-8') as fh:
                m = re.match(r'\[(.*?) -- \d+ pages\]', fh.readline())
        except OSError:
            continue
        nombre = re.sub(r'^\s*([IVX]+|\d+)\s*-\s*', '', re.sub(r'\.(docx\.)?pdf$', '', m.group(1), flags=re.I)) if m else ''
        if clave and re.sub(r'[^a-z0-9]+', '', slugify(nombre)) == clave:
            candidatos.append(f)
    for f in candidatos:
        if not os.path.isfile(f):
            continue
        with open(f, encoding='utf-8') as fh:
            partes = re.split(r'<<<PAGE (\d+)>>>', fh.read())
        if len(partes) < 3:
            return {1: partes[0]}
        return {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)}
    # Sin txt: del PDF mismo, si hay pypdf (el workflow lo instala).
    ruta = os.path.join(aqui, 'Archivo', archivo)
    if archivo and os.path.isfile(ruta):
        try:
            import pypdf
            return {i + 1: pg.extract_text() or '' for i, pg in enumerate(pypdf.PdfReader(ruta).pages)}
        except Exception:  # sin pypdf o PDF ilegible: sin texto
            pass
    return {}


def sync_corpus_json(corpus, slug, unidades, es_pdf, pdf_names, registro):
    data = cargar_json(CORPUS_PATH, {'obras': []})

    chapters = unidades
    total_acciones = sum(len(acciones_de_capitulo(registro, ch['id'])) for ch in chapters)
    total_diagonales = sum(
        1
        for ch in chapters
        for a in acciones_de_capitulo(registro, ch['id']).values()
        for t in (a.get('tipos') or [])
        if t.get('tipo') == 'diagonal'
    )
    total_words = sum(
        len(re.sub(r'<[^>]+>', '', c.get('body') or '').split())
        for c in chapters
    )
    chapters_sin_body = [resumen_unidad(c, registro, slug) for c in chapters]
    if es_pdf:
        # Un posteo-PDF no tiene cuerpo: las palabras salen del texto del PDF,
        # cada parte con las de sus páginas.
        por_pagina = palabras_pdf(corpus)
        total_words = sum(por_pagina.values())
        for r, c in zip(chapters_sin_body, chapters):
            desde = c.get('paginaDesde') or 1
            hasta = c.get('paginaHasta') or max(por_pagina or {desde: 0})
            r['_palabras'] = sum(n for pg, n in por_pagina.items() if desde <= pg <= hasta)

    obra = {
        'id': slug,
        'tipo_nodo': 'pdf' if es_pdf else 'post',
        'tipo': corpus.get('tipo', 'libro'),
        'categoria': corpus.get('categoria'),
        'titulo': corpus['book']['title'],
        'subtitulo': corpus['book'].get('subtitle'),
        'autor': corpus['book'].get('author', 'Pepi'),
        'fecha_creacion': corpus.get('fecha_creacion') or date.today().isoformat(),
        '_file': slug + '.html',
        '_hasPdf': len(pdf_names) > 0,
        '_chapters': chapters_sin_body,
        '_totalAcciones': total_acciones,
        '_totalDiags': total_diagonales,
        '_totalWords': total_words,
        '_estado': 'publicada' if all(c.get('estado') == 'publicada' for c in chapters) else 'parcial',
        # Índice: "principal" (lo nuevo escrito en la plataforma), "base"
        # (la trayectoria anterior) o "pdf" (el resto, a los costados).
        # Sin elegir: los PDFs van a los costados y lo escrito al centro.
        'seccion': corpus.get('seccion') or ('pdf' if es_pdf else 'principal'),
        'serie': (corpus.get('serie') or '').strip() or None,
        'serie_orden': corpus.get('serie_orden'),
    }
    if (corpus.get('diagonal') or '').strip():
        obra['diagonal'] = corpus['diagonal'].strip()
    # si está marcada para la web (lo usa «eliminar posteos» del índice)
    obra['en_linea'] = corpus.get('en_linea') is True
    if es_pdf:
        obra['_pdfArchivo'] = (corpus.get('pdf') or {}).get('archivo')
        obra['_pdfTotalPaginas'] = (corpus.get('pdf') or {}).get('totalPaginas')
    for campo in ('serie', 'serie_titulo', 'serie_parte'):
        if corpus.get(campo) is not None:
            obra[campo] = corpus[campo]

    existing_idx = next((i for i, o in enumerate(data['obras']) if o.get('id') == slug), None)
    if existing_idx is not None:
        data['obras'][existing_idx] = obra
        accion = 'actualizada'
    else:
        data['obras'].append(obra)
        accion = 'agregada'

    guardar_json(CORPUS_PATH, data)
    return accion, data


def main():
    if len(sys.argv) != 2:
        print('Uso: python3 generar_obra.py <archivo.json>')
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print('No existe:', json_path)
        sys.exit(1)

    with open(json_path, encoding='utf-8') as f:
        corpus = json.load(f)

    if 'book' not in corpus or 'title' not in corpus.get('book', {}):
        print('El JSON no tiene book.title — no es el formato esperado.')
        sys.exit(1)

    es_pdf = corpus.get('tipo') == 'pdf'
    template_path = PDF_TEMPLATE_PATH if es_pdf else TEMPLATE_PATH
    if not os.path.exists(template_path):
        print('Falta ' + os.path.basename(template_path) + ' junto a este script.')
        sys.exit(1)

    if es_pdf:
        archivo_pdf = (corpus.get('pdf') or {}).get('archivo')
        if not archivo_pdf:
            print('✗ Posteo-PDF sin pdf.archivo — elegí el PDF de Archivo/ en el taller y volvé a exportar.')
            sys.exit(1)
        corpus['partes'] = normalizar_partes(corpus.get('partes', []))
        if not corpus['partes']:
            print('✗ Posteo-PDF sin partes — agregá al menos una en el taller y volvé a exportar.')
            sys.exit(1)
        unidades = corpus['partes']
    else:
        corpus['chapters'] = normalizar_capitulos(corpus.get('chapters', []))
        unidades = corpus['chapters']
    slug = slugify(corpus['book']['title'])
    # Dos obras con el mismo título (no teoría en texto y su segunda parte
    # en PDF, obras/nt2.json): el slug del título pisaría a la otra obra
    # (su .html, su entrada en corpus.json y el origen de sus acciones).
    # En ese caso manda el nombre del archivo, que es como las identifican
    # el taller y publicar.py.
    archivo_slug = os.path.splitext(os.path.basename(json_path))[0]
    otra = os.path.join(os.path.dirname(os.path.abspath(json_path)), slug + '.json')
    if archivo_slug != slug and re.fullmatch(r'[a-z0-9-]+', archivo_slug) and os.path.exists(otra):
        slug = archivo_slug

    # Registro global de acciones: se lee, se funde lo nuevo de esta
    # sesión, se valida ANTES de escribir nada.
    registro = cargar_json(ACCIONES_PATH, {'meta': {'sitio': 'p314b', 'version': 1}, 'acciones': {}})
    registro.setdefault('acciones', {})
    fundir_acciones(registro, corpus.get('acciones_nuevas'), slug)
    if not es_pdf:
        corregir_capitulos(registro, unidades, slug)
    # Acciones eliminadas en el taller: salen del registro (solo las de
    # esta obra; un id de otra obra no se toca desde acá).
    for aid in corpus.get('acciones_eliminadas') or []:
        if ((registro['acciones'].get(aid) or {}).get('origen') or {}).get('obra') == slug:
            del registro['acciones'][aid]

    errores = revisar_completitud(unidades, registro)
    if errores:
        print('✗ No se generó nada — hay acciones incompletas en capítulos marcados "publicada":\n')
        for e in errores:
            print('  - ' + e)
        print('\nCompletalas o bajá el capítulo a "listo"/"borrador" y volvé a intentar.')
        sys.exit(1)

    with open(template_path, encoding='utf-8') as f:
        template = f.read()

    corpus_data_actual = cargar_json(CORPUS_PATH, {'obras': []})
    if es_pdf:
        html = build_pdf_html(corpus, slug, template, registro, corpus_data_actual)
    else:
        html = build_obra_html(corpus, slug, template, registro, corpus_data_actual)

    os.makedirs(OBRAS_DIR, exist_ok=True)
    out_path = os.path.join(OBRAS_DIR, slug + '.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    if es_pdf:
        pdf_names = [archivo_pdf]
    else:
        pdf_names = [c['pdfName'] for c in unidades if c.get('pdfName')]
    accion, corpus_data_nueva = sync_corpus_json(corpus, slug, unidades, es_pdf, pdf_names, registro)

    try:
        import terminos
        terminos.escribir()  # «resaltar términos»: nodos y lemas al día
    except Exception as e:  # noqa: BLE001 — no frena la generación
        print('⚠ terminos.json no se actualizó:', e)
    concepto = sincronizar_posteo_diagonal(corpus, slug)
    if concepto:
        print('✓ diagonales.json — #' + concepto + ': su posteo es esta obra')

    # acciones.json se guarda al final, ya con corpus.json actualizado
    # disponible para la próxima corrida (para resolver destinos
    # cruzados de otras obras que apunten a esta).
    guardar_json(ACCIONES_PATH, registro)

    propias = [a for a in registro['acciones'].values() if (a.get('origen') or {}).get('obra') == slug]
    unidad = 'partes' if es_pdf else 'capítulos'
    print('✓ obras/' + slug + '.html generado (' + str(len(unidades)) + ' ' + unidad + ')')
    print('✓ corpus.json — obra "' + slug + '" ' + accion)
    print('✓ acciones.json — ' + str(len(propias)) + ' acciones propias de esta obra en el registro')
    if es_pdf:
        existe = os.path.exists(os.path.join(ARCHIVO_DIR, archivo_pdf))
        if not existe:
            print('\n⚠ El PDF "' + archivo_pdf + '" no está en Archivo/ — la página no va a poder mostrarlo hasta que lo copies ahí.')
    elif pdf_names:
        print('\nRecordá copiar a obras/ los PDFs referenciados:')
        for p in pdf_names:
            existe = os.path.exists(os.path.join(OBRAS_DIR, p))
            marca = '(ya está)' if existe else '(FALTA)'
            print('  - ' + p, marca)


if __name__ == '__main__':
    main()
