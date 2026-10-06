#!/usr/bin/env python3
"""
proponer_cruces.py — propuestas de cruce de la matriz relacional.

Uso (desde sitio/):
    python matriz/proponer_cruces.py [--backend NOMBRE] [--modelo MODELO]
                                     [--dry-run] [--muestra N]

Necesita cache-matriz/pasajes.json (indexar_pasajes.py) y
matriz/instrumentos.json (recalibrar.py). Escribe matriz/propuestas.json.
No toca acciones.json, decisiones.json ni instrumentos.json. Una propuesta
no tiene emergente: este script no escribe emergentes.

── Qué compara ──
El perfil de un instrumento son los emergentes de sus diagonales confirmadas
(o, en una diagonal sin emergente, su título, su sinopsis y los párrafos de
sus dos anclas: ver comun.diagonales_confirmadas)
(y los de las propuestas que aceptaste, o retipaste hacia él, con emergente
y todavía no anclaste),
partidos en trozos de ~50 palabras. Cada pasaje (una página de PDF o un grupo
de párrafos de un post) se parte en ventanas de 40 palabras. Origen y destino
no se comparan entre sí: cada uno se compara con el perfil.

── Puntaje (declarado) ──
Antes de comparar se resta a todos los vectores el promedio de las ventanas
del universo: lo que comparten todas las páginas (registro, sintaxis, tono).
Lo que queda es lo específico de cada texto.

Para cada instrumento I y cada pasaje P:
  activación(P) = máximo coseno entre las ventanas de P y los trozos del
                  perfil de I. La ventana ganadora da la cita; el trozo
                  ganador dice de qué diagonal semilla viene el parecido.
  percentil(P)  = fracción de pasajes del universo con activación menor o
                  igual (0 a 1). Así el umbral no depende del backend. Se
                  calcula por semilla (cada emergente contra su propia
                  distribución) y el pasaje se queda con la mejor: si no, un
                  emergente largo, con más trozos, tapa a uno corto.
  robustez(P)   = activación recalculada después de borrar de la ventana las
                  palabras de contenido que comparte (por raíz, ver
                  comun.raiz) con el trozo ganador, dividida por la
                  activación original (tope 1). Si el parecido era de
                  palabras compartidas, se cae.
Para un par (O, D):
  solape(O, D)  = Jaccard de raíces de contenido entre las dos ventanas.
  total         = 0.4·percentil(O) + 0.4·percentil(D)
                  + 0.2·mín(robustez(O), robustez(D))
El origen es el extremo con más activación. La dirección es convencional: se
puede invertir al aceptar.

── Descartes, en este orden ──
  1. pasaje con robustez < robustez_minima (config.json): parecido léxico.
  2. par del mismo sitio o de la misma obra (un PDF y un post con el mismo
     título cuentan como la misma obra).
  3. par con solape > solape_lexico_maximo (config.json): coincidencia léxica.
  4. total < umbral del instrumento (instrumentos.json, lo calcula
     recalibrar.py; si no hay, umbral_inicial de config.json).
  5. par ya decidido (misma id), o parecido a uno rechazado con el mismo
     instrumento: coseno ≥ 0.90 entre las ventanas de los dos extremos.
  6. diversidad: como mucho max_por_pasaje propuestas por pasaje,
     max_por_par_de_sitios por par de sitios, max_por_obra por obra (si
     está en config.json) y el tope del instrumento, tomando primero las de
     mayor total. Todos los topes son por instrumento.

── Cuántas por instrumento ──
Sin propuestas_total en config.json, cada instrumento tiene el mismo tope:
propuestas_por_instrumento. Con propuestas_total, ese total se reparte
según el peso de cada instrumento (instrumentos.json, lo calcula
recalibrar.py): uno nuevo o poco confirmado propone menos, y sumar
instrumentos no suma propuestas. Cada tope queda entre
propuestas_minimas_por_instrumento (5) y propuestas_por_instrumento.
Los de instrumentos_sin_propuestas (config.json) no proponen nada.
"""
import argparse
import hashlib
import random
import sys
from datetime import datetime

from comun import (
    ACCIONES_PATH, CORPUS_PATH, DECISIONES_PATH, INSTRUMENTOS_PATH, PASAJES_PATH, PROPUESTAS_PATH,
    CacheVectores, backend_desde, cargar_config, cargar_json, diagonales_confirmadas, enmascarar,
    guardar_json, huella, jaccard, palabras_contenido, raices_contenido, requerir, resolver_instrumento,
    trozos, ventanas,
)

PESO_PERCENTIL = 0.4          # para cada extremo
PESO_ROBUSTEZ = 0.2
SIMILITUD_RECHAZO = 0.90
LARGO_VENTANA, PASO_VENTANA = 40, 20
LARGO_CITA, PASO_CITA = 20, 5
MINIMO_TRAS_ENMASCARAR = 5    # palabras de contenido que tienen que quedar

ETIQUETA_BACKEND = {
    'hash': 'hash (trivial, léxico por construcción: solo para probar el pipeline)',
    'spacy-es-lg': 'spacy-es-lg (sustituto: promedio de vectores de palabras, no el modelo real)',
    'sentence-transformers': 'sentence-transformers',
}


def perfiles(registro, acciones, decisiones):
    """instrumento canónico -> trozos {texto, fuente, trozo, empieza}.
    También devuelve las diagonales que no forman perfil y por qué."""
    fuentes, sin_perfil = [], []
    for d in diagonales_confirmadas(acciones):
        fuentes.append((d['tipo'].get('instrumento'), d.get('texto_perfil'), d['id']))
    anclados = set((acciones.get('acciones') or {}).keys())
    for dec in decisiones:
        if dec.get('decision') in ('aceptada', 'retipada') and dec.get('accion') not in anclados:
            fuentes.append((dec.get('instrumento'), dec.get('emergente'), dec.get('propuesta')))

    out, vistos = {}, set()
    for iid, emergente, fuente in fuentes:
        iid = resolver_instrumento(iid, registro)
        if not iid:
            sin_perfil.append((fuente, 'sin instrumento'))
            continue
        if not (emergente or '').strip():
            sin_perfil.append((fuente, 'sin emergente'))
            continue
        if (iid, huella(emergente)) in vistos:
            continue
        vistos.add((iid, huella(emergente)))
        for k, t in enumerate(trozos(emergente)):
            out.setdefault(iid, []).append({'texto': t, 'fuente': fuente, 'trozo': k,
                                            'empieza': ' '.join(t.split()[:8]) + '…'})
    return out, sin_perfil


def describir_semilla(fuente, acciones, titulos):
    """'ac-x (Cero → Términos y condiciones)' para una diagonal semilla."""
    a = (acciones.get('acciones') or {}).get(fuente)
    if not a:
        return '%s (propuesta aceptada)' % fuente
    origen = titulos.get((a.get('origen') or {}).get('obra'), (a.get('origen') or {}).get('obra'))
    destino = None
    for t in a.get('tipos') or []:
        if t.get('tipo') == 'diagonal':
            d = (acciones.get('acciones') or {}).get(t.get('destino')) or {}
            destino = titulos.get((d.get('origen') or {}).get('obra'), (d.get('origen') or {}).get('obra'))
    return '%s (%s → %s)' % (fuente, origen, destino or '?')


def lugar(p, sitios):
    titulo = (sitios.get(p['sitio']) or {}).get('titulo') or p['sitio']
    if p.get('pdf_pagina') is not None:
        return '%s, p. %d' % (titulo, p['pdf_pagina'])
    return '%s (%s)' % (titulo, p.get('capitulo'))


def topes_por_instrumento(ids, por_id, total=None, maximo=40, minimo=5):
    """Tope de propuestas de cada instrumento. Sin total, todos el máximo;
    con total, repartido por peso (calculado.peso de instrumentos.json; el
    que no tiene peso toma la mediana), entre minimo y maximo."""
    ids = list(ids)
    if not total:
        return {i: maximo for i in ids}
    pesos = {i: (por_id.get(i, {}).get('calculado') or {}).get('peso') for i in ids}
    conocidos = sorted(p for p in pesos.values() if p)
    mediana = conocidos[len(conocidos) // 2] if conocidos else 1.0
    pesos = {i: (p if p else mediana) for i, p in pesos.items()}
    suma = sum(pesos.values()) or 1.0
    return {i: max(minimo, min(maximo, round(total * pesos[i] / suma))) for i in ids}


def id_propuesta(a, b, iid):
    par = '|'.join(sorted([a, b]))
    return 'pr-' + hashlib.sha1(('%s|%s' % (par, iid)).encode('utf-8')).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description='Propuestas de cruce de la matriz relacional.')
    ap.add_argument('--backend', help='hash | spacy-es-lg | sentence-transformers (por defecto, el de config.json)')
    ap.add_argument('--modelo', help='modelo del backend (por defecto, el de config.json si el backend coincide)')
    ap.add_argument('--dry-run', action='store_true', help='no escribe propuestas.json')
    ap.add_argument('--muestra', type=int, default=0, help='imprime N propuestas al azar con su explicación')
    args = ap.parse_args()

    np = requerir('numpy', 'Instalalo con: pip install numpy')

    cfg = cargar_config()
    nombre_backend = args.backend or cfg.get('backend', 'sentence-transformers')
    modelo = args.modelo or (cfg.get('modelo') if nombre_backend == cfg.get('backend') else None)
    robustez_minima = float(cfg.get('robustez_minima', 0.8))
    solape_maximo = float(cfg.get('solape_lexico_maximo', 0.2))
    umbral_inicial = float(cfg.get('umbral_inicial', 0.9))
    max_instr = int(cfg.get('propuestas_por_instrumento', 40))
    max_par = int(cfg.get('max_por_par_de_sitios', 3))
    max_pasaje = int(cfg.get('max_por_pasaje', 2))
    max_obra = int(cfg['max_por_obra']) if cfg.get('max_por_obra') else None
    total_cfg = int(cfg['propuestas_total']) if cfg.get('propuestas_total') else None
    min_instr = int(cfg.get('propuestas_minimas_por_instrumento', 5))
    sin_propuestas = set(cfg.get('instrumentos_sin_propuestas') or [])

    indice = cargar_json(PASAJES_PATH, None)
    if not indice:
        raise SystemExit('Falta cache-matriz/pasajes.json: corré antes python matriz/indexar_pasajes.py')
    pasajes, sitios = indice['pasajes'], indice['meta'].get('sitios', {})
    registro = cargar_json(INSTRUMENTOS_PATH, None)
    if registro is None:
        print('  (no hay matriz/instrumentos.json: corré python matriz/recalibrar.py; uso umbral_inicial)')
        registro = {'instrumentos': []}
    por_id = {ins['id']: ins for ins in registro.get('instrumentos', [])}
    acciones = cargar_json(ACCIONES_PATH, {'acciones': {}})
    decisiones = cargar_json(DECISIONES_PATH, {'decisiones': []}).get('decisiones', [])
    titulos = {o['id']: o.get('titulo') for o in cargar_json(CORPUS_PATH, {'obras': []}).get('obras', [])}

    trozos_por_instr, sin_perfil = perfiles(registro, acciones, decisiones)
    callados = sorted(i for i in trozos_por_instr if i in sin_propuestas)
    for iid in callados:
        del trozos_por_instr[iid]
    topes = topes_por_instrumento(trozos_por_instr, por_id, total_cfg, max_instr, min_instr)
    semillas_sin_perfil = [ins['id'] for ins in registro.get('instrumentos', [])
                           if ins.get('semilla') and ins['id'] not in trozos_por_instr]

    backend = backend_desde(nombre_backend, modelo)
    cache = CacheVectores(backend)

    print('── proponer_cruces.py ──')
    print('backend: %s%s' % (nombre_backend, ' · ' + getattr(backend, 'modelo', '') if getattr(backend, 'modelo', '') else ''))
    print('universo: %d pasajes de %d sitios' % (len(pasajes), len(sitios)))
    if callados:
        print('sin propuestas (config.json): %s' % ', '.join(callados))
    if total_cfg:
        print('tope total: %d, repartido por peso (%s)' % (total_cfg, ', '.join('%s %d' % kv for kv in sorted(topes.items()))))

    todas = [(i, v) for i, p in enumerate(pasajes) for v in ventanas(p['texto'], LARGO_VENTANA, PASO_VENTANA)]
    # las ventanas de cada pasaje quedan contiguas: [inicios[i], finales[i])
    cuantas = np.bincount(np.array([i for i, _ in todas]), minlength=len(pasajes))
    if cuantas.min() < 1:
        raise SystemExit('Hay pasajes vacíos en cache-matriz/pasajes.json: volvé a correr indexar_pasajes.py')
    finales = np.cumsum(cuantas)
    inicios = finales - cuantas
    crudos = cache.vectores([v for _, v in todas])
    promedio = crudos.mean(axis=0)

    def centrar(m):
        m = m - promedio
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return m / n

    V = centrar(crudos)
    print('ventanas: %d' % len(todas))

    decididas = {d.get('propuesta') for d in decisiones}
    propuestas, resumen = [], {}

    for iid, perfil in sorted(trozos_por_instr.items()):
        ins = por_id.get(iid, {})
        umbral = float((ins.get('calculado') or {}).get('umbral') or umbral_inicial)
        T = centrar(cache.vectores([t['texto'] for t in perfil]))
        S = V @ T.T
        # Percentil por semilla: cada emergente se mide contra su propia
        # distribución en el universo, para que uno largo (más trozos, más
        # chances de un máximo alto) no tape a uno corto. Cada pasaje se
        # queda con la semilla que mejor lo ubica.
        percentil = np.zeros(len(pasajes))
        act = np.full(len(pasajes), -1.0)
        ventana_de = np.full(len(pasajes), -1)
        trozo_de = np.full(len(pasajes), -1)
        for fuente in dict.fromkeys(t['fuente'] for t in perfil):
            cols = np.array([k for k, t in enumerate(perfil) if t['fuente'] == fuente])
            sim = S[:, cols].max(axis=1)
            act_f = np.maximum.reduceat(sim, inicios)
            pct_f = np.searchsorted(np.sort(act_f), act_f, side='right') / len(act_f)
            for i in np.nonzero(pct_f > percentil)[0]:
                w = inicios[i] + int(sim[inicios[i]:finales[i]].argmax())
                percentil[i], act[i], ventana_de[i] = pct_f[i], act_f[i], w
                trozo_de[i] = cols[int(S[w, cols].argmax())]

        # Solo pueden llegar al umbral los pasajes con percentil suficiente
        # aun con el otro extremo y la robustez perfectos.
        piso = (umbral - PESO_PERCENTIL - PESO_ROBUSTEZ) / PESO_PERCENTIL
        cand = [i for i in range(len(pasajes)) if percentil[i] >= piso and ventana_de[i] >= 0]

        cuenta = {'candidatos': len(cand), 'lexico_pasaje': 0, 'mismo_sitio': 0, 'lexico_par': 0,
                  'bajo_umbral': 0, 'decididas': 0, 'parecidas_a_rechazo': 0, 'diversidad': 0}
        info = {}
        enmascarados = {}
        for i in cand:
            w = ventana_de[i]
            k = trozo_de[i]
            texto = todas[w][1]
            compartidas = raices_contenido(texto) & raices_contenido(perfil[k]['texto'])
            masc = enmascarar(texto, compartidas)
            enmascarados[i] = (masc, k)
            info[i] = {'ventana': texto, 'trozo': int(k), 'compartidas': sorted(compartidas)}
        vm = centrar(cache.vectores([m for m, _ in enmascarados.values()])) if enmascarados else []
        robustos = []
        for (i, (masc, k)), v in zip(enmascarados.items(), vm):
            if len(palabras_contenido(masc)) < MINIMO_TRAS_ENMASCARAR or act[i] <= 0:
                rob = 0.0
            else:
                rob = min(1.0, float(v @ T[k]) / float(act[i]))
            info[i]['robustez'] = rob
            if rob < robustez_minima:
                cuenta['lexico_pasaje'] += 1
            else:
                robustos.append(i)

        # rechazos con este instrumento: vectores de sus dos extremos
        idx_pasaje = {p['id']: i for i, p in enumerate(pasajes)}
        rechazos = []
        for dec in decisiones:
            if dec.get('decision') != 'rechazada':
                continue
            if resolver_instrumento(dec.get('instrumento_propuesto') or dec.get('instrumento'), registro) != iid:
                continue
            extremos = []
            for lado in ('origen', 'destino'):
                e = dec.get(lado) or {}
                j = idx_pasaje.get(e.get('pasaje'))
                if j is not None and ventana_de[j] >= 0:
                    extremos.append(V[ventana_de[j]])
                elif e.get('cita'):
                    extremos.append(centrar(cache.vectores([e['cita']]))[0])
            if len(extremos) == 2:
                rechazos.append(extremos)

        raices = {i: raices_contenido(info[i]['ventana']) for i in robustos}
        pares = []
        for a_pos, a in enumerate(robustos):
            for b in robustos[a_pos + 1:]:
                pa, pb = pasajes[a], pasajes[b]
                if pa['sitio'] == pb['sitio'] or pa['obra_clave'] == pb['obra_clave']:
                    cuenta['mismo_sitio'] += 1
                    continue
                solape = jaccard(raices[a], raices[b])
                if solape > solape_maximo:
                    cuenta['lexico_par'] += 1
                    continue
                total = (PESO_PERCENTIL * percentil[a] + PESO_PERCENTIL * percentil[b]
                         + PESO_ROBUSTEZ * min(info[a]['robustez'], info[b]['robustez']))
                if total < umbral:
                    cuenta['bajo_umbral'] += 1
                    continue
                o, d = (a, b) if act[a] >= act[b] else (b, a)
                pid = id_propuesta(pasajes[o]['id'], pasajes[d]['id'], iid)
                if pid in decididas:
                    cuenta['decididas'] += 1
                    continue
                vo, vd = V[ventana_de[o]], V[ventana_de[d]]
                if any(min(float(vo @ r0), float(vd @ r1)) >= SIMILITUD_RECHAZO
                       or min(float(vo @ r1), float(vd @ r0)) >= SIMILITUD_RECHAZO for r0, r1 in rechazos):
                    cuenta['parecidas_a_rechazo'] += 1
                    continue
                pares.append((float(total), o, d, float(solape), pid))

        pares.sort(key=lambda x: -x[0])
        por_pasaje, por_par, por_obra, elegidos = {}, {}, {}, []
        for par in pares:
            _, o, d, _, _ = par
            so, sd = pasajes[o]['sitio'], pasajes[d]['sitio']
            clave_par = tuple(sorted([so, sd]))
            if (len(elegidos) >= topes[iid] or por_pasaje.get(o, 0) >= max_pasaje
                    or por_pasaje.get(d, 0) >= max_pasaje or por_par.get(clave_par, 0) >= max_par
                    or (max_obra and (por_obra.get(so, 0) >= max_obra or por_obra.get(sd, 0) >= max_obra))):
                cuenta['diversidad'] += 1
                continue
            elegidos.append(par)
            por_pasaje[o] = por_pasaje.get(o, 0) + 1
            por_pasaje[d] = por_pasaje.get(d, 0) + 1
            por_par[clave_par] = por_par.get(clave_par, 0) + 1
            por_obra[so] = por_obra.get(so, 0) + 1
            por_obra[sd] = por_obra.get(sd, 0) + 1

        # cita corta: el tramo de ~20 palabras de la ventana más parecido al trozo
        def cita(i):
            partes = ventanas(info[i]['ventana'], LARGO_CITA, PASO_CITA)
            if len(partes) == 1:
                return partes[0]
            vs = centrar(cache.vectores(partes))
            return partes[int((vs @ T[info[i]['trozo']]).argmax())]

        for total, o, d, solape, pid in elegidos:
            extremos = {}
            for lado, i in (('origen', o), ('destino', d)):
                p = pasajes[i]
                e = {'pasaje': p['id'], 'sitio': p['sitio'], 'tipo_nodo': p['tipo_nodo'], 'cita': cita(i)}
                if p.get('pdf_pagina') is not None:
                    e['pdf_pagina'] = p['pdf_pagina']
                if p.get('capitulo'):
                    e['capitulo'] = p['capitulo']
                extremos[lado] = e
            to, td = perfil[info[o]['trozo']], perfil[info[d]['trozo']]
            semillas = list(dict.fromkeys([to['fuente'], td['fuente']]))
            ro, rd = info[o]['robustez'], info[d]['robustez']
            por_que = (
                'Las dos anclas se parecen al perfil de «%s», armado con el emergente de %s: %s está en el '
                'percentil %d del universo y %s en el %d. El parecido se sostiene al sacar las palabras que '
                'cada una comparte con el emergente (robustez %.2f y %.2f) y entre sí comparten pocas palabras '
                '(solape %.2f).' % (
                    ins.get('etiqueta') or iid,
                    ' y '.join(describir_semilla(s, acciones, titulos) for s in semillas),
                    lugar(pasajes[o], sitios), round(percentil[o] * 100),
                    lugar(pasajes[d], sitios), round(percentil[d] * 100), ro, rd, solape))
            propuestas.append({
                'id': pid,
                'origen': extremos['origen'],
                'destino': extremos['destino'],
                'instrumento': iid,
                'instrumento_estatuto': ins.get('estatuto'),
                'puntaje': {
                    'total': round(total, 3),
                    'percentil_origen': round(float(percentil[o]), 3),
                    'percentil_destino': round(float(percentil[d]), 3),
                    'activacion_origen': round(float(act[o]), 3),
                    'activacion_destino': round(float(act[d]), 3),
                    'robustez_origen': round(ro, 3),
                    'robustez_destino': round(rd, 3),
                    'solape_lexico_par': round(solape, 3),
                    'umbral': round(umbral, 3),
                },
                'explicacion': {
                    'semillas': semillas,
                    'trozos': [
                        {'extremo': 'origen', 'diagonal': to['fuente'], 'trozo': to['trozo'], 'empieza': to['empieza']},
                        {'extremo': 'destino', 'diagonal': td['fuente'], 'trozo': td['trozo'], 'empieza': td['empieza']},
                    ],
                    'palabras_compartidas_con_el_emergente': {
                        'origen': info[o]['compartidas'][:12], 'destino': info[d]['compartidas'][:12]},
                    'por_que': por_que,
                },
                'estatuto': 'inferencia-matriz',
                'backend': ETIQUETA_BACKEND.get(nombre_backend, nombre_backend)
                           + (' · ' + getattr(backend, 'modelo', '') if getattr(backend, 'modelo', '') else ''),
            })
        cuenta['propuestas'] = len(elegidos)
        cuenta['trozos_de_perfil'] = len(perfil)
        cuenta['umbral'] = round(umbral, 3)
        resumen[iid] = cuenta

    cache.guardar()

    salida = {
        'meta': {
            'generado': datetime.now().isoformat(timespec='seconds'),
            'backend': nombre_backend,
            'modelo': getattr(backend, 'modelo', None),
            'universo': indice['meta'].get('universo'),
            'pasajes': len(pasajes),
            'estatuto': 'inferencia-matriz',
            'mostrar_propuestas': bool(cfg.get('mostrar_propuestas', False)),
            'formula': 'total = 0.4·percentil(origen) + 0.4·percentil(destino) + 0.2·mín(robustez); '
                       'ver el encabezado de matriz/proponer_cruces.py',
            'parametros': {'robustez_minima': robustez_minima, 'solape_lexico_maximo': solape_maximo,
                           'umbral_inicial': umbral_inicial, 'propuestas_por_instrumento': max_instr,
                           'propuestas_total': total_cfg, 'propuestas_minimas_por_instrumento': min_instr,
                           'instrumentos_sin_propuestas': callados, 'topes': topes,
                           'max_por_par_de_sitios': max_par, 'max_por_pasaje': max_pasaje, 'max_por_obra': max_obra,
                           'similitud_rechazo': SIMILITUD_RECHAZO, 'ventana': [LARGO_VENTANA, PASO_VENTANA]},
            'por_instrumento': resumen,
            'sitios': {k: {'titulo': sitios[k].get('titulo'), 'tipo_nodo': sitios[k].get('tipo_nodo'),
                           'publicado': sitios[k].get('publicado')}
                       for k in sorted({p[l]['sitio'] for p in propuestas for l in ('origen', 'destino')}) if k in sitios},
            'sin_perfil': {'diagonales': [{'id': f, 'motivo': m} for f, m in sin_perfil],
                           'instrumentos_semilla': semillas_sin_perfil},
        },
        'propuestas': propuestas,
    }

    for iid, c in resumen.items():
        print('\n%s  (umbral %.3f, %d trozos de perfil)' % (iid, c['umbral'], c['trozos_de_perfil']))
        print('  pasajes candidatos (percentil suficiente): %d' % c['candidatos'])
        print('  descartados por parecido léxico del pasaje: %d' % c['lexico_pasaje'])
        print('  pares descartados: mismo sitio/obra %d · solape léxico %d · bajo umbral %d · ya decididos %d · '
              'parecidos a un rechazo %d · diversidad %d' % (
                  c['mismo_sitio'], c['lexico_par'], c['bajo_umbral'], c['decididas'],
                  c['parecidas_a_rechazo'], c['diversidad']))
        print('  propuestas: %d' % c['propuestas'])
    if sin_perfil:
        print('\ndiagonales que no forman perfil: ' + ', '.join('%s (%s)' % x for x in sin_perfil))
    if semillas_sin_perfil:
        print('instrumentos semilla sin emergentes (no pueden proponer todavía): ' + ', '.join(semillas_sin_perfil))
    if not trozos_por_instr:
        print('\nNingún instrumento tiene emergentes: no hay con qué proponer.')

    if args.muestra and propuestas:
        rnd = random.Random(314)
        print('\n── muestra de %d propuestas al azar (semilla fija 314) ──' % min(args.muestra, len(propuestas)))
        for n, p in enumerate(rnd.sample(propuestas, min(args.muestra, len(propuestas))), 1):
            pu = p['puntaje']
            print('\n%d. %s  [%s · total %.3f]' % (n, p['id'], p['instrumento'], pu['total']))
            for lado in ('origen', 'destino'):
                e = p[lado]
                print('   %-7s %s\n           «%s»' % (lado, lugar(e, sitios), e['cita']))
            print('   por qué: ' + p['explicacion']['por_que'])
            comp = p['explicacion']['palabras_compartidas_con_el_emergente']
            print('   palabras que comparte con el emergente (se sacaron para medir robustez): origen %s · destino %s' % (
                ', '.join(comp['origen']) or '—', ', '.join(comp['destino']) or '—'))

    if args.dry_run:
        print('\n(--dry-run: no se escribió propuestas.json)')
    else:
        guardar_json(PROPUESTAS_PATH, salida)
        print('\n✓ matriz/propuestas.json: %d propuestas' % len(propuestas))


if __name__ == '__main__':
    sys.exit(main())
