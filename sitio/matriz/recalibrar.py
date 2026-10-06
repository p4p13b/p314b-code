#!/usr/bin/env python3
"""
recalibrar.py — registro único de instrumentos + pesos y umbrales.

Uso (desde sitio/):
    python matriz/recalibrar.py [--dry-run]

Lee acciones.json (diagonales confirmadas), matriz/decisiones.json (tus
decisiones sobre propuestas) y, solo la primera vez, subgrafo.json. Escribe
matriz/instrumentos.json. Nunca toca acciones.json ni decisiones.json.

── Qué es a mano y qué es calculado ──
A mano (vos): descripcion, alias, semilla, etiqueta. Este script no las
pisa nunca. Calculado (este script): todo lo que está bajo "calculado".
Los números nunca se escriben a mano.

── Qué cuenta ──
Solo lo que tiene estatuto "autor": diagonales de acciones.json y tus
decisiones. Las propuestas (inferencia-matriz) no cuentan.

── Fórmula (declarada; ver PROPUESTA-MATRIZ.md §6) ──
Para cada instrumento I:
  C = diagonales confirmadas con I
  A = propuestas aceptadas con I, o retipadas hacia I (el cruce vale con I)
  R = propuestas de I rechazadas;  T = propuestas de I retipadas a otro
  sitios = sitios distintos tocados por origen y destino de C y A
  Cada caso suma según cuánto dice de tu criterio (EVIDENCIA, abajo): una
  diagonal o una decisión con emergente vale 1; una aceptada de a una sin
  emergente, 0,5; una aceptada en bloque por categoría, 0,15. Una diagonal
  tendida desde una decisión no vuelve a contar (ya contó la decisión). Un
  rechazo en bloque de «sin sustento en el material» o «sin ubicar en el
  índice» no cuenta contra el instrumento: dice que el pasaje no se pudo
  medir, no que el instrumento erró. C, A, R y T siguen siendo cantidades;
  lo ponderado va en «soporte» y «en_contra».
  saturación = soporte / (soporte + 3)
  precisión  = (soporte_A + 1) / (soporte_A + en_contra + 2)   (0.5 sin decisiones)
  dispersión = sitios / total de sitios con anclas (corpus + indexados)
  peso       = 0.5·saturación + 0.3·dispersión + 0.2·precisión
El mismo cálculo se hace por tipo_relacion. Cada tipo dice además cuántas
veces lo usaste vos (de_la_autora: diagonales propias y decisiones de a
una) y cuántas viene solo de aceptar en bloque una categoría de la matriz.

Umbral de propuesta de I, sobre el puntaje total de proponer_cruces.py
(que está en escala de percentiles, 0-1):
  sin decisiones            → umbral_inicial de config.json (0.90)
  solo rechazos             → máx(umbral_inicial, percentil 75 de los rechazados)
  aceptadas y rechazadas    → punto medio entre la mediana de aceptadas y la
                              de rechazadas, acotado a [0.40, 0.99]
  solo aceptadas            → mín(umbral_inicial, mínimo de las aceptadas)
"""
import sys
from datetime import date

from comun import (
    ACCIONES_PATH, CORPUS_PATH, DECISIONES_PATH, INSTRUMENTOS_PATH, PASAJES_PATH, SUBGRAFO_PATH,
    cargar_config, cargar_json, diagonales_confirmadas, guardar_json, lema_propuesto, slugify,
)

# Tabla de migración de PROPUESTA-MATRIZ.md §5 (id viejo del subgrafo ->
# id nuevo). Vacía: los 9 instrumentos del mapeo automático anterior se
# borraron del registro y de subgrafo.json a pedido de la autora (no
# servían). Queda la función por si algún día se importa otro registro.
MIGRACION_SUBGRAFO = {}

MANUALES = ('etiqueta', 'lema', 'descripcion', 'alias', 'semilla')

# Cuánto pesa cada caso en soporte y en contra (ver el encabezado).
EVIDENCIA = {
    'con_emergente': 1.0,       # diagonal o decisión con emergente
    'significante': 0.6,        # diagonal propia sin emergente, nombrada por su título
    'de_a_una': 0.5,            # aceptada (o rechazada) de a una, sin emergente
    'en_bloque': 0.15,          # decidida en bloque por categoría
}
# Rechazos en bloque que no hablan del instrumento sino del material.
SIN_MEDIDA = ('sin sustento en el material', 'sin ubicar en el índice')


def en_bloque(dec):
    return (dec.get('nota') or '').startswith('en bloque')


def evidencia(dec=None, diagonal=None):
    """Cuánto pesa un caso: una diagonal propia o una decisión."""
    t = diagonal or dec or {}
    if (t.get('emergente') or '').strip():
        return EVIDENCIA['con_emergente']
    if diagonal is not None:
        return EVIDENCIA['significante']
    return EVIDENCIA['en_bloque'] if en_bloque(dec) else EVIDENCIA['de_a_una']


def buscar(registro, iid):
    for ins in registro['instrumentos']:
        if ins['id'] == iid or iid in (ins.get('alias') or []):
            return ins
    return None


def alta(registro, iid, etiqueta, estatuto, origen, lema=None, **extra):
    ins = {'id': iid, 'etiqueta': etiqueta or iid,
           'lema': lema or lema_propuesto(etiqueta or iid, registro['instrumentos']),
           'descripcion': None, 'alias': [],
           'estatuto': estatuto, 'semilla': False, 'origen': origen}
    ins.update(extra)
    registro['instrumentos'].append(ins)
    return ins


def importar_subgrafo(registro, altas):
    sub = cargar_json(SUBGRAFO_PATH, None)
    if not sub:
        return
    titulos = {s['id']: s.get('titulo') for s in sub.get('sitios', [])}
    for viejo in sub.get('instrumentos', []):
        if buscar(registro, viejo['id']):
            continue
        nuevo = MIGRACION_SUBGRAFO.get(viejo['id']) or slugify(viejo['id'])
        if buscar(registro, nuevo):
            continue
        evidencia = [dict(e, fuente='evidencia_pulenta') for e in viejo.get('evidencia_pulenta') or []]
        evidencia += [dict(e, fuente='evidencia_texto') for e in viejo.get('evidencia_texto') or []]
        ins = alta(registro, nuevo, viejo.get('label'), 'inferencia-matriz', 'subgrafo.json (mapeo automático, Fases 0-4)',
                   marca_original=viejo.get('estatuto_epistemico'),
                   sitios_declarados=[titulos.get(s, s) for s in viejo.get('sitios') or []],
                   evidencia=evidencia)
        if nuevo != viejo['id']:
            ins['alias'] = [viejo['id']]
        altas.append(nuevo)


def cuenta():
    return {'C': 0, 'A': 0, 'R': 0, 'T': 0, 'sitios': set(), 'aceptadas': [], 'rechazadas': [],
            'soporte': 0.0, 'soporte_A': 0.0, 'en_contra': 0.0, 'autora': 0, 'bloque': 0}


def percentil(valores, q):
    v = sorted(valores)
    if not v:
        return None
    k = (len(v) - 1) * q
    i = int(k)
    return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (k - i)


def mediana(valores):
    return percentil(valores, 0.5)


def calcular(c, total_sitios, umbral_inicial):
    soporte = c['soporte']
    saturacion = soporte / (soporte + 3)
    precision = (c['soporte_A'] + 1) / (c['soporte_A'] + c['en_contra'] + 2)
    dispersion = len(c['sitios']) / total_sitios if total_sitios else 0.0
    peso = round(0.5 * saturacion + 0.3 * dispersion + 0.2 * precision, 3)
    acep, rech = c['aceptadas'], c['rechazadas']
    if acep and rech:
        umbral = max(0.40, min(0.99, (mediana(acep) + mediana(rech)) / 2))
    elif rech:
        umbral = max(umbral_inicial, percentil(rech, 0.75))
    elif acep:
        umbral = min(umbral_inicial, min(acep))
    else:
        umbral = umbral_inicial
    return {'diagonales': c['C'], 'aceptadas': c['A'], 'rechazadas': c['R'], 'retipadas': c['T'],
            'sitios': len(c['sitios']), 'soporte': round(soporte, 2), 'en_contra': round(c['en_contra'], 2),
            'de_la_autora': c['autora'], 'en_bloque': c['bloque'],
            'saturacion': round(saturacion, 3), 'precision': round(precision, 3),
            'dispersion': round(dispersion, 3), 'peso': peso, 'umbral': round(umbral, 3)}


def main():
    dry = '--dry-run' in sys.argv
    cfg = cargar_config()
    umbral_inicial = float(cfg.get('umbral_inicial', 0.9))

    registro = cargar_json(INSTRUMENTOS_PATH, None)
    nuevo_registro = registro is None
    if nuevo_registro:
        registro = {'meta': {}, 'instrumentos': [], 'tipos_relacion': {}}
    altas = []

    diagonales = diagonales_confirmadas()
    for d in diagonales:
        iid = d['tipo'].get('instrumento')
        if iid and not buscar(registro, iid):
            alta(registro, iid, d['tipo'].get('instrumento_nuevo_label'), 'autor', 'taller (diagonal %s)' % d['id'],
                 lema=d['tipo'].get('instrumento_lema'))
            altas.append(iid)

    decisiones = cargar_json(DECISIONES_PATH, {'decisiones': []}).get('decisiones', [])
    for dec in decisiones:
        iid = dec.get('instrumento')
        if iid and not buscar(registro, iid):
            alta(registro, iid, dec.get('instrumento_etiqueta'), 'autor', 'decisión sobre %s' % dec.get('propuesta'),
                 lema=dec.get('instrumento_lema'))
            altas.append(iid)

    if nuevo_registro:
        importar_subgrafo(registro, altas)

    # Todo instrumento tiene lema (se propone si falta; la autora lo corrige
    # en instrumentos.json o desde el taller).
    for ins in registro['instrumentos']:
        if not ins.get('lema'):
            otros = [o for o in registro['instrumentos'] if o is not ins and o.get('lema')]
            ins['lema'] = lema_propuesto(ins.get('etiqueta') or ins['id'], otros)

    corpus = cargar_json(CORPUS_PATH, {'obras': []})
    sitios_totales = {o['id'] for o in corpus.get('obras', [])}
    sitios_totales |= set((cargar_json(PASAJES_PATH, {'meta': {}}).get('meta') or {}).get('sitios', {}).keys())
    total_sitios = len(sitios_totales)

    por_instr = {ins['id']: cuenta() for ins in registro['instrumentos']}
    por_tipo = {}

    def acumular(iid, tipo_rel, campo, sitios=(), puntaje=None, peso=1.0, autora=False):
        destinos = []
        if iid:
            ins = buscar(registro, iid)
            if ins:
                destinos.append(por_instr[ins['id']])
        if tipo_rel:
            destinos.append(por_tipo.setdefault(tipo_rel, cuenta()))
        for c in destinos:
            c[campo] += 1
            c['sitios'].update(s for s in sitios if s)
            if campo in ('C', 'A'):
                c['soporte'] += peso
                if campo == 'A':
                    c['soporte_A'] += peso
                c['autora' if autora else 'bloque'] += 1
            else:
                c['en_contra'] += peso
            if puntaje is not None and campo in ('A', 'R', 'T'):
                (c['aceptadas'] if campo == 'A' else c['rechazadas']).append(puntaje)

    acciones_por_id = cargar_json(ACCIONES_PATH, {'acciones': {}}).get('acciones') or {}
    decididas = {dec.get('propuesta') for dec in decisiones}
    for d in diagonales:
        # tendida desde una decisión: ya cuenta como esa decisión
        if d['tipo'].get('decision') in decididas:
            continue
        destino = acciones_por_id.get(d['tipo'].get('destino')) or {}
        sitios = [d['origen'].get('obra'), (destino.get('origen') or {}).get('obra')]
        acumular(d['tipo'].get('instrumento'), (d['tipo'].get('tipo_relacion') or '').strip(), 'C', sitios,
                 peso=evidencia(diagonal=d['tipo']), autora=True)

    for dec in decisiones:
        puntaje = (dec.get('puntaje') or {}).get('total')
        sitios = [(dec.get('origen') or {}).get('sitio'), (dec.get('destino') or {}).get('sitio')]
        tipo_rel = (dec.get('tipo_relacion') or '').strip()
        peso, autora = evidencia(dec=dec), not en_bloque(dec)
        if dec.get('decision') == 'aceptada':
            acumular(dec.get('instrumento'), tipo_rel, 'A', sitios, puntaje, peso, autora)
        elif dec.get('decision') == 'rechazada':
            sin_medida = en_bloque(dec) and any(x in dec.get('nota') for x in SIN_MEDIDA)
            acumular(dec.get('instrumento_propuesto') or dec.get('instrumento'), None, 'R', (), puntaje,
                     0.0 if sin_medida else peso)
        elif dec.get('decision') == 'retipada':
            # error del instrumento propuesto y acierto del que indicaste;
            # el puntaje se calculó con el perfil del propuesto, así que no
            # entra al umbral del otro
            acumular(dec.get('instrumento_propuesto'), None, 'T', (), puntaje, peso)
            acumular(dec.get('instrumento'), tipo_rel, 'A', sitios, None, peso, autora)

    for ins in registro['instrumentos']:
        ins['calculado'] = calcular(por_instr[ins['id']], total_sitios, umbral_inicial)
    registro['tipos_relacion'] = {k: calcular(v, total_sitios, umbral_inicial) for k, v in sorted(por_tipo.items())}
    registro['meta'] = {
        'descripcion': 'Registro único de instrumentos de la matriz relacional. A mano: etiqueta, descripcion, alias, semilla. '
                       'Calculado por recalibrar.py: todo lo que está bajo "calculado" (nunca a mano). Ver PROPUESTA-MATRIZ.md §5-6.',
        'formula_peso': '0.5·saturación + 0.3·dispersión + 0.2·precisión; saturación=soporte/(soporte+3); '
                        'precisión=(soporte_A+1)/(soporte_A+en_contra+2); dispersión=sitios/total',
        'evidencia': dict(EVIDENCIA, rechazo_sin_medida=0.0, tendida_desde_decision='no vuelve a contar'),
        'total_sitios': total_sitios,
        'recalibrado': date.today().isoformat(),
    }

    print('── recalibrar.py ──')
    print('instrumentos dados de alta: ' + (', '.join(altas) if altas else 'ninguno'))
    for ins in registro['instrumentos']:
        c = ins['calculado']
        print('  %-32s %-18s semilla=%-5s C=%d A=%d R=%d T=%d soporte=%.2f sitios=%d peso=%.3f umbral=%.3f' % (
            ins['id'], ins['estatuto'], ins['semilla'], c['diagonales'], c['aceptadas'], c['rechazadas'], c['retipadas'],
            c['soporte'], c['sitios'], c['peso'], c['umbral']))
    if registro['tipos_relacion']:
        print('tipos de relación: ' + ', '.join('%s (peso %.3f)' % (k, v['peso']) for k, v in registro['tipos_relacion'].items()))
    else:
        print('tipos de relación: ninguno completado todavía')
    if dry:
        print('\n(--dry-run: no se escribió instrumentos.json)')
    else:
        guardar_json(INSTRUMENTOS_PATH, registro)
        print('\n✓ matriz/instrumentos.json actualizado')


if __name__ == '__main__':
    main()
