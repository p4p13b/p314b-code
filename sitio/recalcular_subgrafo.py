#!/usr/bin/env python3
"""
recalcular_subgrafo.py

Fase B del subgrafo relacional. Lee sitio/acciones.json (lo que ya
está publicado/editado) y sitio/subgrafo.json (el registro de
instrumentos), recalcula weight/correlationality/estado de cada
instrumento, y detecta instrumentos nuevos que se hayan etiquetado en
el taller pero todavía no existen en el registro. Reescribe
subgrafo.json — nunca toca acciones.json.

Uso:
    python3 recalcular_subgrafo.py [--dry-run]

--dry-run imprime el resumen sin escribir el archivo.

── Principio de diseño (por pedido explícito de Pepi) ──
El NÚMERO de weight/correlationality es siempre resultado de esta
fórmula — nunca se edita a mano en subgrafo.json. Lo que sí se edita a
mano es qué CUENTA para el cálculo: cada item de evidencia_pulenta /
evidencia_texto tiene un campo "incluir" (default true); ponerlo en
false lo saca del cálculo aunque sea estadísticamente fuerte, para los
casos en que algo es significativo pero improductivo respecto del
material. Los valores de la Fase 3 (mapeo manual, muestreo de Grep)
quedan aparte en weight_seed_fase3 / correlationality_seed_fase3,
como referencia histórica — no alimentan la fórmula.

── Fórmula (honesta, no una caja negra) ──
Por instrumento:
  densidad = sitios_confirmados / total_sitios_declarados
  señal_pulenta = promedio de log(1 + valor) de la evidencia con
                  incluir=true, agrupada por sitio confirmado
                  (freq, weight_cluster y cluster_weight_max se tratan
                  en la misma escala logarítmica — simplificación
                  declarada, no todas las señales de pulenta miden lo
                  mismo pero esta es la Fase B, primera pasada)
  señal_norm    = señal_pulenta / log(1 + 50), tope en 1.0
  weight        = 0.6 * densidad + 0.4 * señal_norm

  correlationality = 1 − (desvío estándar normalizado de señal_pulenta
                     entre los sitios CONFIRMADOS). Manifestación
                     pareja entre sitios puntúa alto; un instrumento
                     fuerte en un sitio y casi ausente en otro puntúa
                     bajo. Con 0 o 1 sitio confirmado no hay paridad
                     que medir → 0.0.

── Escalado autónomo ──
Si una diagonal etiqueta un instrumento.id que YA existe pero en una
obra que no estaba en su lista declarada de sitios, ese sitio se suma
solo (el subgrafo crece con la evidencia real, no con lo que se
declaró en la Fase 0-4). Si una diagonal etiqueta un instrumento.id
que NO existe todavía, se da de alta acá como "instrumento-nuevo-
candidato", estado no_confirmada, para revisión — nunca se promueve
solo a instrumento establecido.
"""
import json
import math
import os
import sys
from util import cargar_json, guardar_json

# Windows con consola no-UTF-8 (cp1252/cp437, típico en cmd.exe o
# PowerShell sin chcp 65001): los símbolos que este script imprime
# (─, ✓, ✗, →) tiran UnicodeEncodeError y cortan la corrida antes de
# escribir subgrafo.json. Se fuerza UTF-8 en stdout/stderr al arrancar.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ACCIONES_PATH = os.path.join(HERE, 'acciones.json')
SUBGRAFO_PATH = os.path.join(HERE, 'subgrafo.json')
CORPUS_PATH = os.path.join(HERE, 'corpus.json')

TECHO_SEÑAL = math.log1p(50)  # constante elegida: 50 menciones ya es señal fuerte de sobra


def construir_slug_a_sitio(subgrafo):
    """slug de obra -> id de sitio del subgrafo, a partir de
    slugs_alias declarados en cada sitio."""
    m = {}
    for sitio in subgrafo.get('sitios', []):
        for alias in sitio.get('slugs_alias', []) or []:
            m[alias] = sitio['id']
    return m


def titulo_desde_corpus(slug, corpus):
    for obra in corpus.get('obras', []):
        if obra.get('id') == slug:
            return obra.get('titulo')
    return None


def recolectar_manifestaciones(acciones, slug_a_sitio):
    """Recorre acciones.json y separa las diagonales instrumentadas en
    dos grupos: manifestaciones de instrumentos que van a existir en
    el registro (por id) y candidatos nuevos (id todavía no
    registrado). Cada manifestación trae el sitio del subgrafo si se
    pudo mapear, o el slug crudo de la obra si no."""
    manifestaciones = {}   # instrumento_id -> {sitio_id_o_slug, ...}

    for accion in (acciones.get('acciones') or {}).values():
        origen = accion.get('origen') or {}
        obra_slug = origen.get('obra')
        for t in accion.get('tipos') or []:
            if t.get('tipo') != 'diagonal':
                continue
            instr_id = t.get('instrumento')
            if not instr_id:
                continue
            sitio_ref = slug_a_sitio.get(obra_slug) or obra_slug or '?'
            manifestaciones.setdefault(instr_id, set()).add(sitio_ref)

    return manifestaciones


def separar_nuevos(manifestaciones, ids_existentes, acciones):
    """De 'manifestaciones' (todo lo etiquetado en acciones.json),
    separa lo que corresponde a instrumentos ya registrados de lo que
    es candidato nuevo, recuperando la etiqueta humana
    (instrumento_nuevo_label) de la acción que lo originó."""
    existentes = {k: v for k, v in manifestaciones.items() if k in ids_existentes}
    nuevos_ids = {k: v for k, v in manifestaciones.items() if k not in ids_existentes}

    nuevos = {}
    if nuevos_ids:
        for accion in (acciones.get('acciones') or {}).values():
            for t in accion.get('tipos') or []:
                if t.get('tipo') != 'diagonal':
                    continue
                iid = t.get('instrumento')
                if iid in nuevos_ids and iid not in nuevos:
                    nuevos[iid] = {
                        'label': t.get('instrumento_nuevo_label') or iid,
                        'sitios': nuevos_ids[iid],
                    }
    return existentes, nuevos


def señal_por_sitio(instr):
    """Agrega evidencia_pulenta + evidencia_texto (solo incluir=true)
    por sitio, sobre una escala logarítmica común — ver docstring del
    módulo para la limitación declarada de esta simplificación."""
    agregada = {}
    for ev in instr.get('evidencia_pulenta') or []:
        if ev.get('incluir', True) is False:
            continue
        s = ev.get('sitio')
        valor = ev.get('freq') or ev.get('weight_cluster') or ev.get('cluster_weight_max') or 0
        agregada[s] = agregada.get(s, 0) + valor
    for ev in instr.get('evidencia_texto') or []:
        if ev.get('incluir', True) is False:
            continue
        s = ev.get('sitio')
        agregada[s] = agregada.get(s, 0) + 1  # una cita de lectura completa cuenta como señal mínima
    return agregada


def calcular_instrumento(instr, confirmados):
    """confirmados: set de sitio_ids del subgrafo (no slugs crudos)
    donde este instrumento tiene al menos una diagonal manifestada."""
    sitios_declarados = set(instr.get('sitios') or [])
    sitios_declarados |= confirmados  # el subgrafo escala solo con la evidencia real
    instr['sitios'] = sorted(sitios_declarados)
    total = len(sitios_declarados)
    n_confirmados = len(confirmados)

    densidad = (n_confirmados / total) if total else 0.0

    agregada = señal_por_sitio(instr)
    valores_confirmados = [math.log1p(agregada.get(s, 0)) for s in confirmados]
    señal_prom = (sum(valores_confirmados) / len(valores_confirmados)) if valores_confirmados else 0.0
    señal_norm = min(1.0, señal_prom / TECHO_SEÑAL) if TECHO_SEÑAL else 0.0

    weight = round(0.6 * densidad + 0.4 * señal_norm, 3)

    if len(valores_confirmados) > 1 and sum(valores_confirmados) > 0:
        media = sum(valores_confirmados) / len(valores_confirmados)
        varianza = sum((v - media) ** 2 for v in valores_confirmados) / len(valores_confirmados)
        desvio_norm = (varianza ** 0.5) / media if media else 1.0
        correlationality = round(max(-1.0, min(1.0, 1 - desvio_norm)), 3)
    else:
        correlationality = 0.0

    if total > 0 and n_confirmados == total:
        estado = 'confirmada'
    elif n_confirmados > 0:
        estado = 'parcial'
    else:
        estado = 'no_confirmada'

    instr['weight'] = weight
    instr['correlationality'] = correlationality
    instr['estado'] = estado
    instr['sitios_confirmados'] = n_confirmados
    instr['total_sitios'] = total
    # Detalle por sitio (no solo el conteo): lo necesita matriz.html
    # (Fase E) para pintar cada arista según esté confirmada por una
    # diagonal real o solo declarada desde el mapeo original.
    instr['sitios_confirmados_ids'] = sorted(confirmados)


def registrar_sitios_faltantes(subgrafo, corpus, manifestaciones, slug_a_sitio):
    """Si una manifestación cae en un slug de obra que no mapea a
    ningún sitio declarado, se da de alta un sitio nuevo (usa el slug
    como id, busca el título real en corpus.json si existe) — así el
    subgrafo cubre el sitio entero, no solo los 9 del situado
    original."""
    slugs_conocidos = set(slug_a_sitio.keys())
    slugs_vistos = set()
    for sitios in manifestaciones.values():
        for s in sitios:
            if s not in {sit['id'] for sit in subgrafo['sitios']} and s not in slugs_conocidos:
                slugs_vistos.add(s)

    nuevos = []
    for slug in sorted(slugs_vistos):
        if slug == '?':
            continue
        titulo = titulo_desde_corpus(slug, corpus) or slug
        subgrafo['sitios'].append({
            'id': slug,
            'titulo': titulo,
            'slug_probable': slug,
            'slugs_alias': [slug],
            'estado_en_sitio': 'generada',
            'codigo_confirmado': True,
            'hueco_fase0': False,
            'notas': 'sitio detectado automáticamente por recalcular_subgrafo.py — no pertenecía al situado original (Fase 0-4)',
        })
        nuevos.append(slug)
    return nuevos


def main():
    dry_run = '--dry-run' in sys.argv

    acciones = cargar_json(ACCIONES_PATH, {'acciones': {}})
    subgrafo = cargar_json(SUBGRAFO_PATH, None)
    corpus = cargar_json(CORPUS_PATH, {'obras': []})
    if subgrafo is None:
        print('✗ No existe sitio/subgrafo.json — nada para recalcular.')
        sys.exit(1)

    slug_a_sitio = construir_slug_a_sitio(subgrafo)
    manifestaciones_crudas = recolectar_manifestaciones(acciones, slug_a_sitio)

    # Sitios nuevos detectados por evidencia real (fuera del situado original)
    sitios_nuevos = registrar_sitios_faltantes(subgrafo, corpus, manifestaciones_crudas, slug_a_sitio)
    if sitios_nuevos:
        slug_a_sitio = construir_slug_a_sitio(subgrafo)  # se recalcula con los nuevos sitios ya dados de alta

    # Traducir manifestaciones a ids de sitio (ahora que sitios nuevos ya
    # existen). Descarta '?' — diagonal sin origen.obra resuelto (no
    # debería pasar una vez que generar_obra.py fundió la acción, pero
    # no se cuenta como sitio confirmado si por algo pasara).
    manifestaciones = {}
    for iid, refs in manifestaciones_crudas.items():
        traducidas = {slug_a_sitio.get(r, r) for r in refs if r != '?'}
        if traducidas:
            manifestaciones[iid] = traducidas

    ids_existentes = {i['id'] for i in subgrafo['instrumentos']}
    existentes, nuevos_candidatos = separar_nuevos(manifestaciones, ids_existentes, acciones)

    resumen = []
    for instr in subgrafo['instrumentos']:
        confirmados = existentes.get(instr['id'], set())
        antes = (instr.get('weight'), instr.get('estado'))
        calcular_instrumento(instr, confirmados)
        resumen.append((instr['id'], antes, (instr['weight'], instr['estado'])))

    altas = []
    for cand_id, info in nuevos_candidatos.items():
        sitios_ordenados = sorted(info['sitios'])
        nuevo = {
            'id': cand_id,
            'label': info['label'],
            'tipo': 'instrumento-nuevo-candidato',
            'en_grafo_fase7': False,
            'estatuto_epistemico': '[hipótesis no verificada]',
            'sitios': [],  # calcular_instrumento lo llena con 'confirmados' abajo
            'evidencia_pulenta': [],
            'evidencia_texto': [],
            'weight_seed_fase3': None,
            'correlationality_seed_fase3': None,
            'type': 'emergente',
            'bridge': 'Instrumento detectado automáticamente por recalcular_subgrafo.py a partir de diagonales etiquetadas en el taller — sin evidencia de pulenta todavía, revisión manual pendiente.',
        }
        # Pasa por la misma fórmula que los instrumentos existentes —
        # nada de números especiales para los candidatos nuevos, un
        # solo camino de cálculo para todo el registro.
        calcular_instrumento(nuevo, set(sitios_ordenados))
        subgrafo['instrumentos'].append(nuevo)
        altas.append(cand_id)

    print('── recalcular_subgrafo.py ──')
    if sitios_nuevos:
        print('sitios nuevos detectados: ' + ', '.join(sitios_nuevos))
    else:
        print('sitios nuevos detectados: ninguno')
    if altas:
        print('instrumentos nuevos dados de alta: ' + ', '.join(altas))
    else:
        print('instrumentos nuevos dados de alta: ninguno')
    print('')
    for iid, antes, despues in resumen:
        if antes != despues:
            print(f'  {iid}: weight {antes[0]}→{despues[0]}  estado {antes[1]}→{despues[1]}')
    sin_cambios = sum(1 for _, a, d in resumen if a == d)
    print(f'\n{len(resumen) - sin_cambios} instrumento(s) actualizados, {sin_cambios} sin cambios.')

    if dry_run:
        print('\n(--dry-run: no se escribió subgrafo.json)')
    else:
        guardar_json(SUBGRAFO_PATH, subgrafo)
        print('\n✓ sitio/subgrafo.json actualizado')


if __name__ == '__main__':
    main()
