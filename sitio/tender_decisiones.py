#!/usr/bin/env python3
"""tender_decisiones.py — convierte en diagonal las relaciones de la matriz
que la autora mandó a tender desde la bandeja del taller.

En la bandeja, «tender como diagonal» marca la decisión (tender: true en
matriz/decisiones.json). Este script, para cada decisión marcada:

  1. Pone un ancla en cada punta, en el pasaje de la cita:
     - en un posteo-PDF, una acción anclada a la página (pdf_pagina), en
       la parte que contiene esa página;
     - en un texto escrito, una marca (<span class="accion-mark">) sobre
       el pasaje, buscado palabra por palabra en sus capítulos. Si el
       pasaje cruza una etiqueta (una cursiva, un salto), se marca su
       tramo más largo sin cortes. Si la cita no está entera (vino de la
       transcripción del PDF y el texto escrito difiere en algo), se marca
       el tramo más largo que sí está, si es al menos la mitad.
     Un sitio de la matriz que es un PDF del archivo se ancla en el
     posteo-PDF que lo publica.
  2. Tiende la diagonal entre las dos anclas, ida y vuelta, con el tipo de
     relación y el instrumento de la decisión. Con emergente, lleva ese
     emergente tal cual; sin emergente, es un ancla de diagonal vacía.
  3. Anota en la decisión la acción de ida (accion) y la fecha (tendida),
     y le saca la marca.

Si una punta no se puede anclar (la cita no aparece, el sitio no es una
obra del taller, la página no está en ninguna parte del PDF), no toca
nada de esa decisión: le saca la marca y deja el motivo en tender_aviso,
así vuelve a la bandeja con el aviso.

No cambia ninguna palabra de los textos: la marca solo envuelve un pasaje
que ya está.

    python3 tender_decisiones.py            tiende las marcadas
    python3 tender_decisiones.py --prueba   solo dice qué haría
"""
import html
import json
import os
import random
import re
import string
import sys
import unicodedata
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
DECISIONES = os.path.join(AQUI, 'matriz', 'decisiones.json')
ACCIONES = os.path.join(AQUI, 'acciones.json')
OBRAS = os.path.join(AQUI, 'obras')

PALABRA = re.compile(r'\w+', re.U)
ENTIDAD = re.compile(r'&(#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);')


def leer(ruta):
    with open(ruta, encoding='utf-8') as f:
        texto = f.read()
    return json.loads(texto), texto.endswith('\n')


def escribir(ruta, datos, con_salto):
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        if con_salto:
            f.write('\n')


def nuevo_id(usados):
    while True:
        aid = 'ac-' + ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))
        if aid not in usados:
            usados.add(aid)
            return aid


def palabras_cita(cita):
    """Las palabras de la cita, sin las de los bordes cortados («… pal»)
    ni los «nbsp» que quedaron de la extracción."""
    cita = (cita or '').strip()
    ps = [p.lower() for p in PALABRA.findall(cita) if p.lower() != 'nbsp']
    if cita.startswith('…') and len(ps) > 4:
        ps = ps[1:]
    if cita.endswith('…') and len(ps) > 4:
        ps = ps[:-1]
    return ps


def texto_con_mapa(body):
    """El texto plano de un cuerpo HTML y, para cada carácter, dónde empieza
    y termina en el HTML y en qué tramo sin etiquetas está."""
    plano, ini, fin, tramo = [], [], [], []
    i, n, t = 0, len(body), 0
    while i < n:
        c = body[i]
        if c == '<':
            j = body.find('>', i)
            j = n if j < 0 else j + 1
            # un salto de bloque separa palabras
            plano.append(' '); ini.append(i); fin.append(i); tramo.append(-1)
            i = j
            t += 1
            continue
        m = ENTIDAD.match(body, i) if c == '&' else None
        if m:
            ch = html.unescape(m.group(0))
            ch = ' ' if ch == '\xa0' else ch
            for x in ch:
                plano.append(x); ini.append(i); fin.append(m.end()); tramo.append(t)
            i = m.end()
            continue
        plano.append(' ' if c == '\xa0' else c); ini.append(i); fin.append(i + 1); tramo.append(t)
        i += 1
    return ''.join(plano), ini, fin, tramo


def buscar_en_cuerpo(body, ps):
    """(inicio, fin) en el HTML del pasaje de palabras ps, dentro de un
    solo tramo sin etiquetas; None si no aparece."""
    if not ps:
        return None
    plano, ini, fin, tramo = texto_con_mapa(body)
    toks = [(m.group(0).lower(), m.start(), m.end()) for m in PALABRA.finditer(plano)]
    toks = [t for t in toks if t[0] != 'nbsp']
    k = len(ps)
    for a in range(len(toks) - k + 1):
        if toks[a][0] != ps[0] or [t[0] for t in toks[a:a + k]] != ps:
            continue
        s, e = toks[a][1], toks[a + k - 1][2]
        # El tramo más largo sin etiquetas dentro de [s, e).
        mejor, i = None, s
        while i < e:
            if tramo[i] < 0:
                i += 1
                continue
            j = i
            while j < e and tramo[j] == tramo[i]:
                j += 1
            seg = plano[i:j].strip()
            if seg and (not mejor or len(seg) > mejor[2]):
                li = i + (len(plano[i:j]) - len(plano[i:j].lstrip()))
                lj = j - (len(plano[i:j]) - len(plano[i:j].rstrip()))
                mejor = (li, lj, len(seg))
            i = j
        if mejor:
            return ini[mejor[0]], fin[mejor[1] - 1], plano[mejor[0]:mejor[1]]
    return None


def slug(s):
    """Como slugPropuesta del taller: así nombra la matriz a cada sitio."""
    s = unicodedata.normalize('NFD', str(s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


_ALIAS = None


def obra_de_sitio(sitio):
    """El slug de la obra del taller para un sitio de la matriz: el mismo
    nombre o, si el sitio es un PDF del archivo, el posteo-PDF que lo
    publica («sí teoría.pdf» → si-teoria-pdf)."""
    global _ALIAS
    if os.path.exists(os.path.join(OBRAS, f'{sitio}.json')):
        return sitio
    if _ALIAS is None:
        _ALIAS = {}
        for nombre in sorted(os.listdir(OBRAS)):
            if not nombre.endswith('.json') or nombre.endswith('-citas.json'):
                continue
            try:
                with open(os.path.join(OBRAS, nombre), encoding='utf-8') as f:
                    o = json.load(f)
            except (OSError, ValueError):
                continue
            archivo = ((o.get('pdf') or {}).get('archivo') or '') if isinstance(o, dict) else ''
            if archivo:
                _ALIAS.setdefault(slug(re.sub(r'\.pdf$', '', archivo, flags=re.I)), nombre[:-5])
    return _ALIAS.get(sitio)


def tramo_comun(body, ps):
    """El tramo más largo de palabras seguidas de la cita que aparece tal
    cual en el cuerpo (la cita vino de la transcripción del PDF y el texto
    escrito difiere en algún signo o palabra). None si es corto."""
    plano = texto_con_mapa(body)[0]
    toks = [t.lower() for t in PALABRA.findall(plano) if t.lower() != 'nbsp']
    pos = {}
    for i, t in enumerate(toks):
        pos.setdefault(t, []).append(i)
    mejor = []
    for a in range(len(ps)):
        for i in pos.get(ps[a], ()):
            k = 0
            while a + k < len(ps) and i + k < len(toks) and toks[i + k] == ps[a + k]:
                k += 1
            if k > len(mejor):
                mejor = ps[a:a + k]
    return mejor if len(mejor) >= max(6, len(ps) // 2) else None


def anclar(punta, obras, usados):
    """Prepara el ancla de una punta. Devuelve (cambio, aviso): cambio es
    lo que hay que escribir si las dos puntas se pueden anclar."""
    sitio = obra_de_sitio(punta.get('sitio')) if punta.get('sitio') else None
    if not sitio:
        return None, f'«{punta.get("sitio")}» no es una obra del taller'
    ruta = os.path.join(OBRAS, f'{sitio}.json')
    if sitio not in obras:
        obras[sitio] = leer(ruta)
    obra = obras[sitio][0]
    aid = nuevo_id(usados)
    if obra.get('tipo') == 'pdf':
        pag = punta.get('pdf_pagina')
        if pag is None:
            return None, f'la cita de «{sitio}» no dice en qué página está'
        parte = next((p for p in obra.get('partes') or []
                      if (p.get('paginaDesde') or 0) <= pag <= (p.get('paginaHasta') or 0)), None)
        if not parte:
            return None, f'la página {pag} de «{sitio}» no está en ninguna de sus partes'
        frag = ' '.join(PALABRA.findall(punta.get('cita') or '')) or f'p. {pag}'
        return {'sitio': sitio, 'id': aid, 'origen': {'obra': sitio, 'capitulo': parte['id'], 'fragmento': frag, 'pdf_pagina': pag}}, None
    ps = palabras_cita(punta.get('cita'))
    caps = obra.get('chapters') or []
    # Primero el capítulo que nombra la decisión, después los demás.
    nombre = (punta.get('capitulo') or '').strip().lower()
    caps = sorted(caps, key=lambda c: (str(c.get('title') or '').strip().lower() != nombre))
    # Tal cual; si no, el tramo más largo de la cita que sí está (al menos
    # la mitad de sus palabras, y no menos de seis).
    for exacta in (True, False):
        for ch in caps:
            body = ch.get('body') or ''
            sub = ps if exacta else tramo_comun(body, ps)
            r = buscar_en_cuerpo(body, sub) if sub else None
            if r:
                a, b, frag = r
                return {'sitio': sitio, 'id': aid, 'capitulo': ch['id'], 'html': (a, b),
                        'origen': {'obra': sitio, 'capitulo': ch['id'], 'fragmento': frag}}, None
    return None, f'la cita no aparece en el texto de «{sitio}» (¿se corrigió el texto?)'


def diagonal(d, destino, reciproca_de=None):
    emergente = d.get('emergente') if (d.get('emergente') or '').strip() else ''
    t = {'tipo': 'diagonal', 'via': 'ancla-diagonal', 'modo': 'unico', 'lemas': [], 'tags': [],
         'tipo_relacion': d.get('tipo_relacion') or None, 'instrumento': d.get('instrumento') or None,
         'instrumento_nuevo_label': None, 'destino': destino, 'emergente': emergente,
         'paneles': {'fuente': {'visible': True}, 'diagonal': {'visible': True}, 'remitente': {'visible': True}},
         'decision': d.get('propuesta')}
    if not emergente:
        t['vacia'] = True
    if reciproca_de:
        t['reciproca_de'] = reciproca_de
    return t


def aplicar(cambio, tipos, obras, registro):
    obra = obras[cambio['sitio']][0]
    aid = cambio['id']
    if 'html' in cambio:
        ch = next(c for c in obra['chapters'] if c['id'] == cambio['capitulo'])
        a, b = cambio['html']
        body = ch['body']
        ch['body'] = body[:a] + f'<span class="accion-mark" data-accion="{aid}">' + body[a:b] + '</span>' + body[b:]
    accion = {'id': aid, 'origen': dict(cambio['origen']), 'tipos': [{'tipo': 'ancla-diagonal'}] + tipos}
    nuevas = obra.get('acciones_nuevas')
    if not isinstance(nuevas, dict):
        nuevas = obra['acciones_nuevas'] = {}
    nuevas[aid] = accion
    registro['acciones'][aid] = json.loads(json.dumps(accion))


def main():
    prueba = '--prueba' in sys.argv
    dec, salto_dec = leer(DECISIONES)
    marcadas = [d for d in dec.get('decisiones') or [] if d.get('tender') and not d.get('accion')]
    if not marcadas:
        print('tender: no hay decisiones marcadas para tender.')
        return 0
    registro, salto_reg = leer(ACCIONES)
    usados = set(registro.get('acciones') or {})
    obras, tocadas = {}, set()
    hoy = date.today().isoformat()
    hechas = 0
    # Por si una decisión ya se tendió y volvió marcada (un guardado desde
    # una sesión vieja del taller): no se tiende dos veces.
    ya = {t.get('decision'): aid for aid, a in registro['acciones'].items()
          for t in a.get('tipos') or [] if t.get('tipo') == 'diagonal' and t.get('decision') and not t.get('reciproca_de')}
    for d in marcadas:
        if d.get('propuesta') in ya:
            print(f'  · {d.get("propuesta")}: ya estaba tendida ({ya[d["propuesta"]]})')
            if not prueba:
                d.pop('tender', None)
                d['accion'] = ya[d['propuesta']]
            continue
        a, aviso_a = anclar(d.get('origen') or {}, obras, usados)
        b, aviso_b = (None, None) if aviso_a else anclar(d.get('destino') or {}, obras, usados)
        aviso = aviso_a or aviso_b
        if aviso:
            print(f'  ✗ {d.get("propuesta")}: {aviso}')
            d.pop('tender', None)
            d['tender_aviso'] = aviso
            continue
        mismo_cap = 'html' in a and 'html' in b and a['sitio'] == b['sitio'] and a['capitulo'] == b['capitulo']
        if mismo_cap and not (a['html'][1] <= b['html'][0] or b['html'][1] <= a['html'][0]):
            aviso = 'las dos citas caen en el mismo pasaje'
            print(f'  ✗ {d.get("propuesta")}: {aviso}')
            d.pop('tender', None)
            d['tender_aviso'] = aviso
            continue
        print(f'  ✓ {d.get("propuesta")}: {a["sitio"]} «{a["origen"]["fragmento"][:50]}» ↔ {b["sitio"]} «{b["origen"]["fragmento"][:50]}»'
              + ('' if (d.get('emergente') or '').strip() else ' (vacía)'))
        hechas += 1
        if prueba:
            continue
        # En el mismo capítulo, primero la marca que está más adelante, así
        # no se corren las posiciones de la otra.
        orden = [(a, [diagonal(d, b['id'])]), (b, [diagonal(d, a['id'], reciproca_de=a['id'])])]
        if mismo_cap and a['html'][0] < b['html'][0]:
            orden.reverse()
        for cambio, tipos in orden:
            aplicar(cambio, tipos, obras, registro)
            tocadas.add(cambio['sitio'])
        d.pop('tender', None)
        d.pop('tender_aviso', None)
        d['accion'] = a['id']
        d['tendida'] = hoy
    print(f'tender: {hechas} de {len(marcadas)} se pueden tender' + (' (prueba: no se escribió nada)' if prueba else ''))
    if prueba:
        return 0
    for sitio in tocadas:
        escribir(os.path.join(OBRAS, f'{sitio}.json'), *obras[sitio])
    escribir(ACCIONES, registro, salto_reg)
    escribir(DECISIONES, dec, salto_dec)
    return 0


if __name__ == '__main__':
    sys.exit(main())
