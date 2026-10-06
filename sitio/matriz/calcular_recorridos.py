#!/usr/bin/env python3
"""
calcular_recorridos.py — recorridos sobre el grafo de diagonales confirmadas.

Uso (desde sitio/):
    python matriz/calcular_recorridos.py [--dry-run]

Lee acciones.json (las diagonales, estatuto autor), corpus.json (títulos y
orden de los sitios) y matriz/instrumentos.json (pesos, los calcula
recalibrar.py). Escribe matriz/recorridos.json. Las propuestas no entran: un
recorrido pasa solo por diagonales que escribiste. No copia emergentes: cada
paso nombra su diagonal y la página los lee de acciones.json.

── Grafo ──
Nodo: un ancla (una acción de acciones.json: un fragmento de un post o una
página de un PDF). Arista: una diagonal, del ancla de origen al ancla de
destino. Dos anclas del mismo sitio están a mano: quien llega a una puede
seguir desde la otra sin salir de la obra.

── Cómo se encadena un recorrido (igual para todos los criterios) ──
Dado un conjunto de diagonales D, ya ordenado por el criterio:
  1. se empieza por la primera diagonal de D;
  2. desde el ancla de llegada se sigue, en este orden de preferencia:
     a) una diagonal de D que sale de esa misma ancla;
     b) una que sale de otra ancla del mismo sitio;
     c) si no hay, el recorrido salta a la siguiente diagonal de D sin
        recorrer (el paso lleva "salto": true);
  3. entre varias posibles gana la primera según el orden del criterio.
Cada diagonal se recorre una sola vez.

── Criterios ──
  instrumento    un recorrido por instrumento, con sus diagonales. Orden:
                 sitio de origen (orden de corpus.json), después id.
  tipo_relacion  uno por cada etiqueta de tipo_relacion que completaste,
                 mismo orden. Las diagonales sin tipo_relacion no entran.
  peso           todas las diagonales, de mayor a menor peso. Peso de una
                 diagonal = peso de su instrumento (instrumentos.json); si
                 tiene tipo_relacion, el promedio con el peso de ese tipo.
                 Empates: mismo orden que "instrumento".
  deriva         DERIVAS recorridos al azar, con semilla declarada (1, 2,
                 3…): se baraja D y se encadena igual; como mucho
                 LARGO_DERIVA pasos.
"""
import random
import sys
from datetime import datetime

from comun import (
    ACCIONES_PATH, CORPUS_PATH, INSTRUMENTOS_PATH, RECORRIDOS_PATH,
    cargar_json, diagonales_confirmadas, guardar_json, resolver_instrumento, slugify,
)

DERIVAS = 3
LARGO_DERIVA = 12


def ancla(aid, accion, titulos):
    o = (accion or {}).get('origen') or {}
    a = {'accion': aid, 'sitio': o.get('obra'), 'titulo': titulos.get(o.get('obra'), o.get('obra')),
         'capitulo': o.get('capitulo'), 'fragmento': o.get('fragmento'), 'pdf_pagina': o.get('pdf_pagina'),
         'url': 'obras/%s.html#accion=%s' % (o.get('obra'), aid)}
    return {k: v for k, v in a.items() if v is not None}


def encadenar(diagonales):
    pendientes, pasos, llegada = list(diagonales), [], None
    while pendientes:
        elegida, salto = None, False
        if llegada is not None:
            elegida = next((d for d in pendientes if d['desde']['accion'] == llegada['accion']), None)
            if elegida is None:
                elegida = next((d for d in pendientes if d['desde'].get('sitio') == llegada.get('sitio')), None)
        if elegida is None:
            elegida, salto = pendientes[0], llegada is not None
        pendientes.remove(elegida)
        pasos.append({'diagonal': elegida['id'], 'desde': elegida['desde'], 'hacia': elegida['hacia'],
                      'instrumento': elegida['instrumento'], 'tipo_relacion': elegida['tipo_relacion'],
                      'salto': salto})
        llegada = elegida['hacia']
    return pasos


def recorrido(rid, criterio, valor, etiqueta, pasos, **extra):
    r = {'id': rid, 'criterio': criterio, 'valor': valor, 'etiqueta': etiqueta,
         'pasos': pasos, 'saltos': sum(1 for p in pasos if p['salto'])}
    r.update(extra)
    return r


def main():
    dry = '--dry-run' in sys.argv
    acciones = cargar_json(ACCIONES_PATH, {'acciones': {}})
    por_id = acciones.get('acciones') or {}
    obras = cargar_json(CORPUS_PATH, {'obras': []}).get('obras', [])
    titulos = {o['id']: o.get('titulo') for o in obras}
    orden_sitio = {o['id']: n for n, o in enumerate(obras)}
    registro = cargar_json(INSTRUMENTOS_PATH, {'instrumentos': [], 'tipos_relacion': {}})
    etiquetas = {ins['id']: ins.get('etiqueta') or ins['id'] for ins in registro.get('instrumentos', [])}
    peso_instr = {ins['id']: (ins.get('calculado') or {}).get('peso') for ins in registro.get('instrumentos', [])}
    peso_tipo = {k: v.get('peso') for k, v in (registro.get('tipos_relacion') or {}).items()}

    diagonales, sin_resolver = [], []
    for d in diagonales_confirmadas(acciones):
        destino = d['tipo'].get('destino')
        if destino not in por_id:
            sin_resolver.append({'diagonal': d['id'], 'destino': destino})
            continue
        diagonales.append({
            'id': d['id'],
            'desde': ancla(d['id'], por_id[d['id']], titulos),
            'hacia': ancla(destino, por_id[destino], titulos),
            'instrumento': resolver_instrumento(d['tipo'].get('instrumento'), registro),
            'tipo_relacion': (d['tipo'].get('tipo_relacion') or '').strip() or None,
        })

    def clave(d):
        return (orden_sitio.get(d['desde'].get('sitio'), len(orden_sitio)), d['desde'].get('sitio') or '', d['id'])

    def peso(d):
        p = peso_instr.get(d['instrumento']) or 0.0
        if d['tipo_relacion'] and peso_tipo.get(d['tipo_relacion']) is not None:
            p = (p + peso_tipo[d['tipo_relacion']]) / 2
        return p

    diagonales.sort(key=clave)
    recorridos = []
    for iid in dict.fromkeys(d['instrumento'] for d in diagonales if d['instrumento']):
        grupo = [d for d in diagonales if d['instrumento'] == iid]
        recorridos.append(recorrido('instrumento:' + iid, 'instrumento', iid, etiquetas.get(iid, iid), encadenar(grupo)))
    for tipo in sorted({d['tipo_relacion'] for d in diagonales if d['tipo_relacion']}):
        grupo = [d for d in diagonales if d['tipo_relacion'] == tipo]
        recorridos.append(recorrido('tipo:' + slugify(tipo), 'tipo_relacion', tipo, tipo, encadenar(grupo)))
    if diagonales:
        por_peso = sorted(diagonales, key=lambda d: (-peso(d),) + clave(d))
        recorridos.append(recorrido('peso', 'peso', None, 'por peso', encadenar(por_peso),
                                    pesos={d['id']: round(peso(d), 3) for d in por_peso}))
        for semilla in range(1, DERIVAS + 1):
            barajadas = list(diagonales)
            random.Random(semilla).shuffle(barajadas)
            recorridos.append(recorrido('deriva:%d' % semilla, 'deriva', semilla, 'a la deriva %d' % semilla,
                                        encadenar(barajadas)[:LARGO_DERIVA], semilla=semilla))

    anclas = {d['desde']['accion'] for d in diagonales} | {d['hacia']['accion'] for d in diagonales}
    sitios = {d['desde'].get('sitio') for d in diagonales} | {d['hacia'].get('sitio') for d in diagonales}
    salida = {
        'meta': {
            'generado': datetime.now().isoformat(timespec='seconds'),
            'descripcion': 'Recorridos sobre el grafo de diagonales confirmadas (estatuto autor). '
                           'Criterios y encadenamiento declarados en matriz/calcular_recorridos.py.',
            'diagonales': len(diagonales), 'anclas': len(anclas), 'sitios': len(sitios),
            'derivas': {'cantidad': DERIVAS, 'largo_maximo': LARGO_DERIVA, 'semillas': list(range(1, DERIVAS + 1))},
            'sin_resolver': sin_resolver,
            'sin_tipo_relacion': sum(1 for d in diagonales if not d['tipo_relacion']),
        },
        'recorridos': recorridos,
    }

    print('── calcular_recorridos.py ──')
    print('%d diagonales, %d anclas, %d sitios' % (len(diagonales), len(anclas), len(sitios)))
    if sin_resolver:
        print('diagonales con destino sin resolver (no entran): ' + ', '.join(x['diagonal'] for x in sin_resolver))
    for r in recorridos:
        print('  %-36s %2d pasos, %d saltos: %s' % (r['id'], len(r['pasos']), r['saltos'], ' → '.join(
            ('⤳ ' if p['salto'] else '') + '%s→%s' % (p['desde'].get('sitio'), p['hacia'].get('sitio')) for p in r['pasos'])))
    if not any(r['criterio'] == 'tipo_relacion' for r in recorridos):
        print('  (por tipo de relación: ninguna diagonal tiene tipo_relacion todavía)')
    if dry:
        print('\n(--dry-run: no se escribió recorridos.json)')
    else:
        guardar_json(RECORRIDOS_PATH, salida)
        print('\n✓ matriz/recorridos.json: %d recorridos' % len(recorridos))


if __name__ == '__main__':
    main()
