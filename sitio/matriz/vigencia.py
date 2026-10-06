#!/usr/bin/env python3
"""
vigencia.py — qué textos que lee el Cowork siguen vivos en el sitio, y con
qué nombre.

Uso (desde sitio/):
    python matriz/vigencia.py [--dry-run]

Escribe matriz/vigencia.json (lo corre también cowork.py, en cada
publicación) e imprime el diagnóstico. No toca ningún texto, obra,
decisión ni archivo de la papelera: solo lee.

── Por qué ──
Varios textos cambiaron de nombre o de forma («sí teoría» quedó en el
posteo «pop»; «sí» en «.»; los PDF de «Términos y condiciones», «Ni-ni»,
«dos puntos»… se ocultaron porque su texto se publicó escrito). La
matriz seguía proponiendo relaciones hacia esos nombres viejos, que no
van a aparecer en el sitio.

── Cómo decide, para cada texto de datos-lee/txt ──
  vivo       tiene un posteo en línea (PDF o escrito) con su nombre: ese
             es su sitio («1021.pdf» → 1-0-2-1).
  alias      no tiene posteo propio en línea, pero al menos la mitad de su
             texto (tramos de 8 palabras) está en un posteo escrito en
             línea: ese es su sitio («dos puntos» → «:»).
  repartido  ningún posteo tiene la mitad, pero entre varios sí: su sitio
             es el que más tiene («bardo»).
  poemario   poemarios y poemas: quedan como estaban (no entran en esta
             depuración).
  muerto     nada de lo anterior: la matriz no propone ni relaciona hacia
             él. Va a la lista de textos que faltarían subir.
equivalencias.json manda sobre el cálculo («forzar») y traduce nombres
viejos que menciona el Cowork («Proyecto» → «sí teoría»).

── Papelera ──
Un archivo de la papelera es ocioso si borrarlo no pierde nada: su texto
ya está (90 % o más) en un posteo en línea o en un PDF publicado, o es un
posteo-PDF que solo apunta a un PDF de Archivo/ que sigue ahí; y no lleva
acciones que falten en acciones.json. El taller los marca y deja
borrarlos (uno por uno o todos los ociosos); este script no borra nada.

── Faltantes ──
Textos que hipotéticamente faltaría subir: los muertos, los que están
solo en parte (con las páginas que no aparecen), los que el Cowork
nombra sin que haya texto en datos-lee, y lo de la papelera que no está
en ningún lado.
"""
import glob
import html as htmlmod
import json
import os
import re
import sys
import zlib
from collections import defaultdict
from datetime import datetime

from comun import DATOS_LEE_TXT, MATRIZ_DIR, RAIZ_DIR, SITIO_DIR, clave_obra, leer, slugify

OBRAS_DIR = os.path.join(SITIO_DIR, 'obras')
PAPELERA_DIR = os.path.join(SITIO_DIR, 'papelera')
ACCIONES = os.path.join(SITIO_DIR, 'acciones.json')
DECISIONES = os.path.join(MATRIZ_DIR, 'decisiones.json')
EQUIVALENCIAS = os.path.join(MATRIZ_DIR, 'equivalencias.json')
SALIDA = os.path.join(MATRIZ_DIR, 'vigencia.json')
COWORK = os.path.join(RAIZ_DIR, 'datos-lee', 'cowork')

TEJA = 8
MUESTRA = 3            # se guarda 1 de cada 3 tramos (por su hash): misma proporción, un tercio de memoria
UMBRAL_ALIAS = 0.5
UMBRAL_OCIOSA = 0.9
UMBRAL_PAGINA = 0.5    # una página "está" en el posteo si la mitad de sus tramos está
POEMARIO = re.compile(r'poe?a?mario|poema', re.I)
PALABRA = re.compile(r"[\wñÑ]+(?:['’][\w]+)?")


def texto_plano(html):
    html = re.sub(r'(?is)<(style|script|xml)\b.*?</\1>|<!--.*?-->', ' ', html or '')
    return htmlmod.unescape(re.sub(r'<[^>]+>', ' ', html)).replace('\xa0', ' ')


def tejas(texto):
    """Tramos de 8 palabras (sin tildes ni mayúsculas), como enteros
    estables; solo los que caen en la muestra."""
    w = [slugify(m.group(0)) for m in PALABRA.finditer(texto)]
    w = [x for x in w if x]
    out = set()
    for i in range(len(w) - TEJA + 1):
        h = zlib.crc32(' '.join(w[i:i + TEJA]).encode())
        if h % MUESTRA == 0:
            out.add(h)
    return out


def solape(a, b):
    return len(a & b) / len(a) if a else 0.0


def rangos(nums):
    """[1,2,3,7,9,10] → "1-3, 7, 9-10"."""
    nums, out = sorted(nums), []
    for n in nums:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ', '.join(str(a) if a == b else f'{a}-{b}' for a, b in out)


# ───────── Lo que hay ─────────

def unidades_publicadas(o):
    us = (o.get('partes') if o.get('tipo') == 'pdf' else o.get('chapters')) or []
    return [u for u in us if u.get('estado') == 'publicada']


def obras_taller():
    """Cada obra de obras/: si está en línea, su PDF (clave) y su texto
    publicado (los posteos escritos)."""
    out = {}
    for ruta in sorted(glob.glob(os.path.join(OBRAS_DIR, '*.json'))):
        if ruta.endswith('-citas.json'):
            continue
        o = leer(ruta, None)
        if not isinstance(o, dict):
            continue
        slug = os.path.basename(ruta)[:-5]
        es_pdf = o.get('tipo') == 'pdf'
        pubs = unidades_publicadas(o)
        archivo = (o.get('pdf') or {}).get('archivo') or ''
        out[slug] = {
            'titulo': (o.get('book') or {}).get('title') or slug,
            'pdf': es_pdf, 'categoria': o.get('categoria') or '',
            'vivo': o.get('en_linea') is True and bool(pubs),
            'clave_pdf': clave_obra(archivo) if archivo else None,
            'texto': '' if es_pdf else '\n'.join(texto_plano(u.get('body')) for u in pubs),
        }
    return out


def textos_archivo():
    """Cada .txt de datos-lee: su nombre (cabecera), clave y páginas."""
    out = {}
    for ruta in sorted(glob.glob(os.path.join(DATOS_LEE_TXT, '*', '*.txt'))):
        with open(ruta, encoding='utf-8', errors='replace') as f:
            crudo = f.read()
        m = re.match(r'\[(.*?) -- ', crudo)
        nombre = m.group(1) if m else os.path.basename(ruta)
        partes = re.split(r'<<<PAGE (\d+)>>>', crudo)
        paginas = {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)} or {1: crudo.split('\n', 1)[-1]}
        titulo = re.sub(r'\.(docx\.)?(pdf|png|docx)$', '', nombre, flags=re.I)
        titulo = re.sub(r'^\s*([IVX]+|\d+)\s*-\s*', '', titulo).rstrip('_ ').strip()
        out[os.path.relpath(ruta, RAIZ_DIR)] = {'titulo': titulo, 'clave': clave_obra(nombre), 'nombre': nombre,
                                                 'carpeta': os.path.basename(os.path.dirname(ruta)), 'paginas': paginas}
    return out


# ───────── Cálculo ─────────

def calcular():
    eq = leer(EQUIVALENCIAS, {}) or {}
    forzar = {clave_obra(k): v for k, v in (eq.get('forzar') or {}).items()}
    taller = obras_taller()
    archivo = textos_archivo()
    registro = (leer(ACCIONES, {}) or {}).get('acciones') or {}

    vivos_texto = {s: tejas(o['texto']) for s, o in taller.items() if o['vivo'] and not o['pdf'] and o['texto'].strip()}
    por_clave = defaultdict(list)
    for s, o in taller.items():
        if o['clave_pdf']:
            por_clave[o['clave_pdf']].append(s)

    # ── Textos del archivo ──
    res, tejas_archivo = {}, {}
    for ruta, a in archivo.items():
        propios = sorted(por_clave.get(a['clave'], []), key=lambda s: (not taller[s]['vivo'], s))
        poema = any(POEMARIO.search(taller[s]['categoria']) for s in propios)
        paginas = {n: tejas(t) for n, t in a['paginas'].items()}
        todo = tejas_archivo[ruta] = set().union(*paginas.values()) if paginas else set()
        en = sorted(((solape(todo, V), s) for s, V in vivos_texto.items()), reverse=True)
        en = [(f, s) for f, s in en if f >= 0.01]
        union = solape(todo, set().union(*(vivos_texto[s] for _, s in en))) if en else 0.0
        r = {'titulo': a['titulo'], 'nombre': a['nombre'], 'carpeta': a['carpeta'], 'posteos': propios,
             'en': [{'sitio': s, 'solape': round(f, 3)} for f, s in en[:4]]}
        if a['clave'] in forzar:
            r.update(estado='alias' if forzar[a['clave']] else 'muerto', vigente=forzar[a['clave']] or None,
                     por='equivalencias.json')
        elif propios and taller[propios[0]]['vivo']:
            r.update(estado='vivo', vigente=propios[0], por='posteo en línea')
        elif en and en[0][0] >= UMBRAL_ALIAS:
            r.update(estado='alias', vigente=en[0][1], por=f'{round(en[0][0] * 100)} % de su texto está en ese posteo')
        elif en and union >= UMBRAL_ALIAS:
            r.update(estado='repartido', vigente=en[0][1],
                     por=f'{round(union * 100)} % de su texto está repartido en ' + ', '.join(s for _, s in en[:4]))
        elif poema:
            r.update(estado='poemario', vigente=propios[0] if propios else None, por='poemario: queda como estaba')
        else:
            r.update(estado='muerto', vigente=None, por='no tiene posteo en línea y su texto no está en ninguno')
        if r['estado'] in ('alias', 'repartido', 'muerto'):
            dentro = set().union(*(vivos_texto[s] for _, s in en)) if en else set()
            r['cobertura'] = round(union, 3)
            fuera = [n for n, T in paginas.items() if len(T) >= 3 and solape(T, dentro) < UMBRAL_PAGINA]
            if fuera and len(paginas) > 1:
                r['paginas_fuera'] = rangos(fuera)
                r['n_paginas_fuera'] = len(fuera)
                r['n_paginas'] = len(paginas)
        res[ruta] = r

    # tramos de los PDF en línea, para la papelera
    vivos_archivo = {}
    for ruta, r in res.items():
        if r['estado'] in ('vivo', 'poemario') and r['vigente'] and taller.get(r['vigente'], {}).get('vivo'):
            vivos_archivo[ruta] = tejas_archivo[ruta]

    # ── Nombres de sitio viejos → vigente ──
    sitios = {}
    for ruta, r in res.items():
        for s in r['posteos'] + [slugify(re.sub(r'\.(docx\.)?pdf$', '', archivo[ruta]['nombre'], flags=re.I)),
                                 slugify(r['titulo']), archivo[ruta]['clave']]:
            if s and not taller.get(s, {}).get('vivo') and s not in sitios:
                sitios[s] = {'vigente': r['vigente'], 'por': f'«{r["titulo"]}» ({r["estado"]})'}
    for s, o in taller.items():
        if o['vivo']:
            sitios[s] = {'vigente': s, 'por': 'posteo en línea'}

    # ── Papelera ──
    papelera = []
    for ruta in sorted(glob.glob(os.path.join(PAPELERA_DIR, '*.json'))):
        nombre = os.path.basename(ruta)
        o = leer(ruta, None)
        m = re.match(r'^\d{8}-\d{6}-(.+)\.json$', nombre)
        p = {'archivo': nombre, 'slug': m.group(1) if m else nombre[:-5]}
        if not isinstance(o, dict):
            papelera.append(dict(p, ociosa=False, motivo='no se pudo leer'))
            continue
        p['titulo'] = (o.get('book') or {}).get('title') or p['slug']
        sueltas = [k for k in (o.get('acciones_nuevas') or {}) if k not in registro]
        if o.get('tipo') == 'pdf':
            arch = (o.get('pdf') or {}).get('archivo') or ''
            ahora = [s for s in por_clave.get(clave_obra(arch), []) if taller[s]['vivo']]
            p['motivo'] = f'posteo-PDF: solo apunta a Archivo/{arch}, que no se borra' + (
                f'; ese PDF lo publica «{taller[ahora[0]]["titulo"]}»' if ahora else '')
            p['ociosa'] = True
        else:
            T = tejas('\n'.join(texto_plano(c.get('body')) for c in o.get('chapters') or []))
            cand = [(solape(T, V), taller[s]['titulo']) for s, V in vivos_texto.items()]
            cand += [(solape(T, V), res[r]['titulo'] + ' (PDF)') for r, V in vivos_archivo.items()]
            mejor = max(cand) if cand and T else (0.0, '')
            p['ociosa'] = bool(T) and mejor[0] >= UMBRAL_OCIOSA
            p['solape'] = round(mejor[0], 3)
            if not T:
                p['motivo'] = 'sin texto'
                p['ociosa'] = True
            elif p['ociosa']:
                p['motivo'] = f'su texto ya está en «{mejor[1]}» ({round(mejor[0] * 100)} %)'
            else:
                # ¿es una versión vieja de un texto del archivo?
                arch_mejor = max(((solape(T, tejas_archivo[r2]), r2)
                                  for r2, r in res.items() if r['estado'] in ('alias', 'repartido', 'muerto')),
                                 default=(0.0, None))
                if arch_mejor[0] >= UMBRAL_OCIOSA:
                    p['version_de'] = res[arch_mejor[1]]['titulo']
                p['motivo'] = (f'solo {round(mejor[0] * 100)} % de su texto está en el sitio (lo más: «{mejor[1]}»)'
                               + (f'; es una versión de «{p["version_de"]}»' if p.get('version_de') else ''))
        if sueltas:
            p['ociosa'] = False
            p['motivo'] += f'; lleva {len(sueltas)} acción(es) que no están en acciones.json'
        papelera.append(p)
    for p in papelera:
        if p['slug'] not in sitios and 'su texto ya está' in p.get('motivo', ''):
            dest = next((s for s, o in taller.items() if o['vivo'] and f'«{o["titulo"]}»' in p['motivo']), None)
            if dest:
                sitios[p['slug']] = {'vigente': dest, 'por': f'papelera: {p["motivo"]}'}

    # ── Faltantes ──
    faltantes = []
    for ruta, r in res.items():
        if r['estado'] == 'muerto' or (r['estado'] in ('alias', 'repartido') and r.get('cobertura', 1) < UMBRAL_OCIOSA):
            f = {'titulo': r['titulo'], 'fuente': ruta, 'estado': r['estado'], 'cobertura': r.get('cobertura', 0.0),
                 'vigente': r['vigente'], 'por': r['por']}
            for k in ('paginas_fuera', 'n_paginas_fuera', 'n_paginas'):
                if k in r:
                    f[k] = r[k]
            f['versiones_en_papelera'] = [p['archivo'] for p in papelera if p.get('version_de') == r['titulo']]
            faltantes.append(f)
    # lo que el Cowork nombra sin texto en datos-lee
    claves = {a['clave'] for a in archivo.values()}
    nombres_eq = {clave_obra(k) for k in (eq.get('nombres') or {})}
    ajenos = {clave_obra(k) for k in (eq.get('ajenos') or {})}
    for rd in sorted(glob.glob(os.path.join(COWORK, 'enlaces', '*-dates.md'))):
        de_clo = 'Clo' in os.path.basename(rd)
        with open(rd, encoding='utf-8') as fh:
            for m in re.finditer(r'^## (.+?)\s+\(\d+ pags', fh.read(), re.M):
                c = clave_obra(re.sub(r'\.docx(?=\.pdf$)', '', m.group(1)))
                if c in claves or c in ajenos or c in nombres_eq or de_clo:
                    continue
                faltantes.append({'titulo': m.group(1), 'fuente': os.path.relpath(rd, RAIZ_DIR), 'estado': 'sin texto',
                                  'cobertura': 0.0, 'vigente': None, 'por': 'el Cowork lo leyó pero no hay su .txt en datos-lee'})
    for p in papelera:
        if not p.get('ociosa') and not p.get('version_de') and p.get('solape', 1) < UMBRAL_ALIAS:
            faltantes.append({'titulo': p.get('titulo') or p['slug'], 'fuente': 'sitio/papelera/' + p['archivo'],
                              'estado': 'papelera', 'cobertura': p.get('solape', 0.0), 'vigente': None, 'por': p['motivo']})

    # ── Decisiones tuyas que apuntan a nombres viejos (solo se listan) ──
    viejas = defaultdict(int)
    for d in (leer(DECISIONES, {}) or {}).get('decisiones') or []:
        for lado in ('origen', 'destino'):
            s = (d.get(lado) or {}).get('sitio')
            if s and not taller.get(s, {}).get('vivo'):
                viejas[s] += 1
    decisiones = [{'sitio': s, 'n': n, 'vigente': (sitios.get(s) or {}).get('vigente')} for s, n in sorted(viejas.items(), key=lambda kv: -kv[1])]

    return {
        'meta': {'generado': datetime.now().isoformat(timespec='seconds'),
                 'umbrales': {'alias': UMBRAL_ALIAS, 'ociosa': UMBRAL_OCIOSA, 'pagina': UMBRAL_PAGINA, 'teja': TEJA},
                 'nota': 'Lo calcula matriz/vigencia.py (ver su encabezado). Solo lee: no borra ni cambia nada.'},
        'archivo': res,
        'sitios': dict(sorted(sitios.items())),
        'papelera': papelera,
        'faltantes': faltantes,
        'decisiones_con_nombre_viejo': decisiones,
    }


def guardar(datos):
    """Escribe vigencia.json solo si cambió algo más que la fecha."""
    previo = leer(SALIDA, None)
    if isinstance(previo, dict):
        a, b = dict(previo.get('meta') or {}), dict(datos['meta'])
        a.pop('generado', None), b.pop('generado', None)
        if a == b and {k: v for k, v in previo.items() if k != 'meta'} == json.loads(json.dumps({k: v for k, v in datos.items() if k != 'meta'})):
            return False
    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write('\n')
    return True


def resumen(d):
    from collections import Counter
    print('── vigencia.py ──')
    print('textos del archivo:', dict(Counter(r['estado'] for r in d['archivo'].values())))
    for r in d['archivo'].values():
        if r['estado'] not in ('vivo', 'poemario'):
            print(f"  {r['estado']:<9} {r['titulo']:<36} → {r['vigente'] or '—'}  ({r['por']})")
    oc = [p for p in d['papelera'] if p.get('ociosa')]
    print(f"papelera: {len(d['papelera'])} archivos, {len(oc)} ociosos")
    for p in d['papelera']:
        print(f"  {'ocioso ' if p.get('ociosa') else 'guardar'} {p['archivo']:<46} {p.get('motivo', '')}")
    print(f"faltantes: {len(d['faltantes'])}")
    for f in d['faltantes']:
        extra = f" · páginas fuera: {f['paginas_fuera']}" if f.get('paginas_fuera') else ''
        print(f"  {f['estado']:<9} {f['titulo']:<36} {round(f['cobertura'] * 100)} % en el sitio{extra}")
    if d['decisiones_con_nombre_viejo']:
        print('decisiones con nombre viejo:', ', '.join(f"{x['sitio']} ({x['n']}) → {x['vigente'] or '—'}" for x in d['decisiones_con_nombre_viejo']))


def main():
    d = calcular()
    resumen(d)
    if '--dry-run' not in sys.argv:
        print('✓ matriz/vigencia.json ' + ('actualizado' if guardar(d) else 'sin cambios'))


if __name__ == '__main__':
    main()
