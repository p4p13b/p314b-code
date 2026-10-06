"""
autonoma.py — expansión autónoma de la matriz: categorías y relaciones que
salen solo del corpus, guardadas aparte y con su origen marcado.

Escribe matriz/autonoma.json. No lee nada de la autora para calcular:
ni instrumentos, ni emergentes, ni diagonales, ni decisiones. Las lee al
final, solo para marcar dónde coincide lo derivado con lo declarado. No
toca ningún archivo de la autora ni los de las otras capas de la matriz.

Entrada: el índice de la superficie relacional (matriz/superficie/,
lo arma anexo/scripts/superficie.py): cada pasaje con su obra, su fecha y
sus 20 claves de mayor tf-idf. Solo Python 3, sin paquetes.

Todos los comandos se corren desde sitio/:  python3 matriz/autonoma.py

Cómo se calcula (todo es repetible: misma entrada, misma salida):

0. Lengua. Esta primera vuelta lee solo los pasajes en castellano (por las
   palabras vacías de cada lengua en el fragmento): en otra lengua las
   claves se agrupan por idioma y no por lo que dicen. Los pasajes en
   inglés, francés e italiano quedan contados en meta, para una vuelta
   propia.
1. Vocabulario. Claves que usan al menos MIN_OBRAS obras y no más de la
   mitad (las de todas partes no distinguen nada), fuera de las vacías.
2. Asociación. Dos claves se asocian si aparecen juntas entre las claves de
   un mismo pasaje más de lo que el azar daría (NPMI sobre pasajes), en al
   menos MIN_PAR_PASAJES pasajes de MIN_PAR_OBRAS obras distintas (un
   idiolecto de una sola obra no es una relación del corpus). Cada clave
   conserva sus VECINOS asociaciones más fuertes.
3. Categorías. Grupos del grafo de asociaciones (Louvain, determinista);
   un grupo demasiado grande se vuelve a partir. Queda si tiene entre
   TAM_MIN y TAM_MAX claves.
   Modo: «sonoro» si la mitad o más de sus claves riman (comparten las
   tres últimas letras) con otra del grupo, sin contar los sufijos de
   derivación (-dad, -ción, -mente…) ni los infinitivos, que comparten
   final por gramática y no por eco; si no, «de sentido». Lo dice el
   material, no una lista: el corpus agrupa tanto por eco como por tema.
4. Nombre. La clave más central del grupo (la de más peso dentro de él), en
   la forma en que más aparece en los textos: el nombre es una palabra del
   propio corpus, nunca una etiqueta de afuera.
5. Dónde está activa. Un pasaje activa una categoría si tiene al menos dos
   de sus claves. Una obra la tiene si la activa en dos pasajes o más (uno,
   si la obra tiene menos de 10). «sobre el azar»: cuántas veces más
   pasajes la activan que conjuntos al azar de claves de frecuencia
   parecida (AZAR_VUELTAS sorteos con semilla fija). Por debajo de
   AZAR_MINIMO no queda.
6. Relaciones entre obras. Dos obras se relacionan por las categorías que
   comparten: cada una suma min(presencia en a, presencia en b) por lo
   específica que es (log de obras totales / obras con la categoría).
   Quedan las que comparten al menos dos categorías, las RELACIONES_MAX
   más fuertes.
7. Cruce con la autora, al final y solo para marcar: si una relación une
   dos obras que ella ya unió con una diagonal (o aceptó en el taller), y si
   el nombre o las claves de una categoría coinciden con un instrumento o un
   concepto diagonal suyo. Nada se mezcla: lo de ella queda en sus archivos.

Origen de cada cosa en la matriz (ver AUTONOMA.md):
  autora              declarado por ella (diagonales, emergentes,
                      instrumentos, decisiones)
  matriz:instrumentos derivado, pero desde los perfiles de sus instrumentos
                      (propuestas.json)
  matriz:corpus       derivado del corpus sin listas de ella (este archivo)
  lector              derivado del recorrido de los visitantes (todavía no)
"""
import collections
import datetime
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (MATRIZ_DIR, SITIO_DIR, ACCIONES_PATH, INSTRUMENTOS_PATH,  # noqa: E402
                   DECISIONES_PATH, cargar_json, guardar_json, slugify,
                   diagonales_confirmadas)

SUPERFICIE = os.path.join(MATRIZ_DIR, 'superficie')
SALIDA = os.path.join(MATRIZ_DIR, 'autonoma.json')
DIAGONALES_PATH = os.path.join(SITIO_DIR, 'diagonales.json')

MIN_OBRAS = 3
MAX_FRACCION_OBRAS = 0.5
MIN_PAR_PASAJES = 3
MIN_PAR_OBRAS = 3
NPMI_MINIMO = 0.2
VECINOS = 8
TAM_MIN, TAM_MAX = 4, 24
AZAR_VUELTAS = 20
AZAR_MINIMO = 2.0
RELACIONES_MAX = 200
EJEMPLOS = 3

# palabras que delatan la lengua de un fragmento (sin las que comparten)
LENGUAS = {
    'es': 'que el los del las por con una para como pero más sus está este esta cuando sin sobre '
          'también ya porque hay donde ni nos fue ser lo se'.split(),
    'en': 'the and of to is you that it my me with this for are was be not but your have what all '
          'from they his her will'.split(),
    'fr': 'les des et est je tu il pas une du qui dans mais pour sur avec nous vous ce sont au ne '
          'elle'.split(),
    'it': 'che non di per sono mi ti io della nel gli come anche questo ma più ho'.split(),
}
LENGUAS = {k: set(v) for k, v in LENGUAS.items()}
# restos de formato que quedaron en algunos .txt (estilos de Word)
FORMATO = set('mso bidi font style tstyle margin family language false true size span div '
              'color align normal times roman arial calibri cambria rowband colband qformat '
              'priority padding table'.split())

# palabras vacías de las otras lenguas: sueltas en un pasaje en castellano
# agrupan por idioma, no por sentido
AJENAS = set().union(*(v for k, v in LENGUAS.items() if k != 'es')) | set(
    'mai moi mon oui toi qui des une est sui vou notre avec'.split())

SUFIJOS = ('dad', 'cion', 'sion', 'mente', 'ncia', 'nte', 'ico', 'ica', 'ivo', 'iva', 'ble',
           'ismo', 'ista', 'oso', 'osa', 'ar', 'er', 'ir', 'arse', 'erse', 'irse')


def gramatical(clave):
    return clave.endswith(SUFIJOS)


def lengua(texto):
    w = re.findall(r"[a-záéíóúñüàèìòùâêîôûç']+", (texto or '').lower())
    cuenta = {k: sum(1 for x in w if x in v) for k, v in LENGUAS.items()}
    mejor = max(cuenta, key=cuenta.get)
    return mejor if cuenta[mejor] else 'es'


# ── Louvain (una implementación chica, determinista) ──

def louvain(nodos, aristas, semilla=0):
    """nodos: lista; aristas: dict {(a, b): peso} con a < b. Devuelve
    {nodo: comunidad}. Orden fijo por semilla: misma entrada, mismo
    resultado."""
    rnd = random.Random(semilla)
    ady = collections.defaultdict(dict)
    for (a, b), w in aristas.items():
        ady[a][b] = ady[a].get(b, 0) + w
        ady[b][a] = ady[b].get(a, 0) + w
    miembros = {n: [n] for n in nodos}
    while True:
        m2 = sum(sum(v.values()) for v in ady.values()) or 1.0
        grado = {n: sum(ady[n].values()) for n in miembros}
        com = {n: n for n in miembros}
        tot = dict(grado)
        orden = sorted(miembros, key=str)
        rnd.shuffle(orden)
        mejoro = True
        movidos = False
        while mejoro:
            mejoro = False
            for n in orden:
                c0 = com[n]
                pesos = collections.defaultdict(float)
                for v, w in ady[n].items():
                    if v != n:
                        pesos[com[v]] += w
                tot[c0] -= grado[n]
                mejor, ganancia = c0, pesos.get(c0, 0) - tot[c0] * grado[n] / m2
                for c, w in sorted(pesos.items(), key=lambda x: str(x[0])):
                    g = w - tot[c] * grado[n] / m2
                    if g > ganancia + 1e-12:
                        mejor, ganancia = c, g
                tot[mejor] += grado[n]
                if mejor != c0:
                    com[n] = mejor
                    mejoro = movidos = True
        if not movidos:
            break
        # agregar: cada comunidad pasa a ser un nodo
        nuevos = collections.defaultdict(list)
        for n, c in com.items():
            nuevos[c].extend(miembros[n])
        ady2 = collections.defaultdict(dict)
        for n, vs in ady.items():
            for v, w in vs.items():
                a, b = com[n], com[v]
                ady2[a][b] = ady2[a].get(b, 0) + w
        ady, miembros = ady2, dict(nuevos)
    return {x: c for c, xs in miembros.items() for x in xs}


def main():
    lex = cargar_json(os.path.join(SUPERFICIE, 'lexico.json'), None)
    pasajes = cargar_json(os.path.join(SUPERFICIE, 'pasajes.json'), None)
    perfil = cargar_json(os.path.join(SUPERFICIE, 'perfil.json'), {}) or {}
    if not lex or not pasajes:
        sys.exit('Falta matriz/superficie/ (lexico.json, pasajes.json): lo arma '
                 'matriz/anexo/scripts/correr.sh o el workflow «Superficie».')

    # 0. lengua
    por_lengua = collections.Counter()
    en_castellano = []
    for p in pasajes:
        l = lengua(p.get('t'))
        por_lengua[l] += 1
        if l == 'es':
            en_castellano.append(p)
    pasajes = en_castellano

    claves, formas, obras_por_clave = lex['claves'], lex['forma'], lex['obras']
    vacias = set((perfil.get('lematizacion') or {}).get('vacias') or [])
    obras_info = perfil.get('obras') or {}
    todas_obras = sorted({p['o'] for p in pasajes})
    N_OBRAS = len(todas_obras)
    pasajes_por_obra = collections.Counter(p['o'] for p in pasajes)

    # 1. vocabulario
    vocab = {i for i, c in enumerate(claves)
             if MIN_OBRAS <= obras_por_clave[i] <= MAX_FRACCION_OBRAS * N_OBRAS
             and c not in vacias and c not in FORMATO and c not in AJENAS and len(c) > 2}

    # claves de cada pasaje dentro del vocabulario (con su peso tf-idf)
    P = []
    for p in pasajes:
        k = p['k']
        ks = {k[j]: k[j + 1] for j in range(0, len(k), 2) if k[j] in vocab}
        P.append(ks)
    n_pas = len(P)

    # 2. asociación (NPMI sobre pasajes, con obras distintas)
    frec = collections.Counter()
    par = collections.Counter()
    par_obras = collections.defaultdict(set)
    for p, ks in zip(pasajes, P):
        orden = sorted(ks)
        frec.update(orden)
        for x in range(len(orden)):
            for y in range(x + 1, len(orden)):
                par[(orden[x], orden[y])] += 1
    for p, ks in zip(pasajes, P):
        orden = sorted(ks)
        for x in range(len(orden)):
            for y in range(x + 1, len(orden)):
                ab = (orden[x], orden[y])
                if par[ab] >= MIN_PAR_PASAJES:
                    par_obras[ab].add(p['o'])
    asoc = {}
    for ab, n in par.items():
        if n < MIN_PAR_PASAJES or len(par_obras[ab]) < MIN_PAR_OBRAS:
            continue
        pab = n / n_pas
        pa, pb = frec[ab[0]] / n_pas, frec[ab[1]] / n_pas
        npmi = math.log(pab / (pa * pb)) / -math.log(pab)
        if npmi >= NPMI_MINIMO:
            asoc[ab] = npmi
    vecinos = collections.defaultdict(list)
    for (a, b), w in asoc.items():
        vecinos[a].append((w, b))
        vecinos[b].append((w, a))
    aristas = {}
    for a, vs in vecinos.items():
        for w, b in sorted(vs, reverse=True)[:VECINOS]:
            aristas[(min(a, b), max(a, b))] = w

    # 3. categorías (Louvain; los grupos grandes se vuelven a partir)
    def partir(nodos, aristas_sub, profundidad=0):
        com = louvain(nodos, aristas_sub)
        grupos = collections.defaultdict(list)
        for n, c in com.items():
            grupos[c].append(n)
        out = []
        for g in grupos.values():
            if len(g) > TAM_MAX and profundidad < 3 and len(g) < len(nodos):
                gs = set(g)
                sub = {ab: w for ab, w in aristas_sub.items() if ab[0] in gs and ab[1] in gs}
                out.extend(partir(g, sub, profundidad + 1))
            else:
                out.append(g)
        return out

    nodos = sorted({x for ab in aristas for x in ab})
    grupos = [g for g in partir(nodos, aristas) if TAM_MIN <= len(g) <= TAM_MAX]

    # índice invertido: clave → pasajes
    inv = collections.defaultdict(list)
    for i, ks in enumerate(P):
        for c in ks:
            inv[c].append(i)

    def activos(conj):
        cuenta = collections.Counter()
        for c in conj:
            cuenta.update(inv[c])
        return [i for i, n in cuenta.items() if n >= 2]

    # sorteo de comparación: claves de frecuencia parecida
    por_frec = sorted(vocab, key=lambda c: (frec[c], c))
    rango = {c: i for i, c in enumerate(por_frec)}
    rnd = random.Random(314)

    def azar(g):
        base = []
        for _ in range(AZAR_VUELTAS):
            conj = set()
            for c in g:
                r = rango.get(c, 0)
                lo, hi = max(0, r - 40), min(len(por_frec) - 1, r + 40)
                conj.add(por_frec[rnd.randint(lo, hi)])
            base.append(len(activos(conj)))
        return max(sum(base) / len(base), 0.5)

    def forma_mas_usada(c):
        f = formas[c] if c < len(formas) else None
        return f or claves[c]

    categorias = []
    for g in grupos:
        gs = set(g)
        interno = collections.defaultdict(float)
        for (a, b), w in aristas.items():
            if a in gs and b in gs:
                interno[a] += w
                interno[b] += w
        g = sorted(g, key=lambda c: (-interno[c], claves[c]))
        act = activos(gs)
        if not act:
            continue
        sobre_azar = len(act) / azar(g)
        if sobre_azar < AZAR_MINIMO:
            continue
        por_obra = collections.Counter(pasajes[i]['o'] for i in act)
        obras = {o: n for o, n in por_obra.items()
                 if n >= 2 or (n >= 1 and pasajes_por_obra[o] < 10)}
        if len(obras) < MIN_OBRAS:
            continue
        pares_int = [w for (a, b), w in aristas.items() if a in gs and b in gs]

        def fuerza(i):
            return sum(P[i][c] for c in gs if c in P[i])
        ejemplos = sorted(act, key=lambda i: (-sum(1 for c in gs if c in P[i]), -fuerza(i), pasajes[i]['id']))
        vistos, ej = set(), []
        for i in ejemplos:
            if pasajes[i]['o'] in vistos:
                continue
            vistos.add(pasajes[i]['o'])
            p = pasajes[i]
            ej.append({'pasaje': p['id'], 'obra': p['o'], 'fecha': p.get('f'),
                       'texto': p.get('t'),
                       'claves': [claves[c] for c in g if c in P[i]]})
            if len(ej) >= EJEMPLOS:
                break
        colas = collections.Counter(claves[c][-3:] for c in g if not gramatical(claves[c]))
        riman = sum(1 for c in g if not gramatical(claves[c]) and colas[claves[c][-3:]] > 1)
        fechas = sorted(pasajes[i]['f'] for i in act if pasajes[i].get('f') is not None)
        categorias.append({
            'nombre': forma_mas_usada(g[0]),
            'nombre_origen': 'corpus: la clave más central del grupo, en su forma más usada',
            'claves': [claves[c] for c in g],
            'formas': [forma_mas_usada(c) for c in g],
            'modo': 'sonoro' if riman * 2 >= len(g) else 'de sentido',
            'cohesion': round(sum(pares_int) / max(len(pares_int), 1), 3),
            'pasajes': len(act),
            'sobre_azar': round(sobre_azar, 2),
            'obras': dict(sorted(((o, round(n / pasajes_por_obra[o], 4)) for o, n in obras.items()),
                                 key=lambda x: -x[1])),
            'desde': fechas[0] if fechas else None,
            'hasta': fechas[-1] if fechas else None,
            'ejemplos': ej,
        })
    # primero lo que atraviesa más obras con más pasajes (lo que articula el
    # corpus), no lo raro de dos o tres textos
    categorias.sort(key=lambda c: (-math.log(c['sobre_azar']) * math.log(1 + c['pasajes'])
                                   * math.log(1 + len(c['obras'])), c['nombre']))
    nombres = collections.Counter()
    for c in categorias:
        nombres[c['nombre']] += 1
        c['id'] = 'mc-' + slugify(c['nombre']) + ('' if nombres[c['nombre']] == 1 else '-%d' % nombres[c['nombre']])

    # 6. relaciones entre obras
    rel = collections.defaultdict(lambda: {'peso': 0.0, 'categorias': []})
    for c in categorias:
        espec = math.log(N_OBRAS / len(c['obras']))
        os_ = sorted(c['obras'])
        for x in range(len(os_)):
            for y in range(x + 1, len(os_)):
                a, b = os_[x], os_[y]
                v = min(c['obras'][a], c['obras'][b]) * espec
                r = rel[(a, b)]
                r['peso'] += v
                r['categorias'].append((v, c['id']))
    relaciones = []
    for (a, b), r in rel.items():
        if len(r['categorias']) < 2:
            continue
        relaciones.append({'a': a, 'b': b, 'peso': round(r['peso'], 4),
                           'categorias': [cid for _, cid in sorted(r['categorias'], reverse=True)]})
    relaciones.sort(key=lambda r: (-r['peso'], r['a'], r['b']))
    relaciones = relaciones[:RELACIONES_MAX]

    # 7. cruce con la autora (solo marca)
    taller = {o: (obras_info.get(o) or {}).get('taller') or o for o in todas_obras}
    de_taller = {v: k for k, v in taller.items()}
    acciones = cargar_json(ACCIONES_PATH, {'acciones': {}})
    todas_acc = acciones.get('acciones') or {}
    pares_autora = collections.Counter()
    for d in diagonales_confirmadas(acciones):
        a = (d['origen'] or {}).get('obra')
        b = ((todas_acc.get(d['tipo'].get('destino') or '') or {}).get('origen') or {}).get('obra')
        if a and b and a != b:
            pares_autora[tuple(sorted((de_taller.get(a, a), de_taller.get(b, b))))] += 1
    aceptadas = collections.Counter()
    for d in (cargar_json(DECISIONES_PATH, {}) or {}).get('decisiones') or []:
        if d.get('decision') not in ('aceptada', 'retipada'):
            continue
        a = (d.get('origen') or {}).get('sitio')
        b = (d.get('destino') or {}).get('sitio')
        if a and b and a != b:
            aceptadas[tuple(sorted((de_taller.get(a, a), de_taller.get(b, b))))] += 1
    for r in relaciones:
        k = (r['a'], r['b'])
        r['autora'] = {'diagonales': pares_autora.get(k, 0), 'aceptadas': aceptadas.get(k, 0)}

    def palabras(s):
        return {w for w in slugify(s).split('-') if len(w) > 2}
    suyas = {}
    for i in (cargar_json(INSTRUMENTOS_PATH, {}) or {}).get('instrumentos') or []:
        if i.get('estatuto') == 'autor':
            for w in palabras(i.get('lema') or '') | palabras(i.get('etiqueta') or ''):
                suyas.setdefault(w, set()).add('instrumento: ' + (i.get('etiqueta') or i['id']))
    for cid, cpt in ((cargar_json(DIAGONALES_PATH, {}) or {}).get('conceptos') or {}).items():
        for w in palabras(cpt.get('nombre') or ''):
            suyas.setdefault(w, set()).add('concepto diagonal: ' + (cpt.get('nombre') or cid))
    for c in categorias:
        hits = set()
        for k in c['claves']:
            for w in palabras(k):
                hits |= suyas.get(w, set())
        c['coincide_con_autora'] = sorted(hits)

    lineas = sum(1 for r in relaciones if not r['autora']['diagonales'] and not r['autora']['aceptadas'])
    salida = {
        'meta': {
            'generado': datetime.datetime.now().isoformat(timespec='seconds'),
            'origen': 'matriz:corpus',
            'estatuto': 'derivado-matriz',
            'descripcion': ('Categorías y relaciones que salen solo del corpus (claves de la '
                            'superficie relacional), sin instrumentos, emergentes, diagonales ni '
                            'decisiones de la autora en el cálculo. Están marcadas como derivadas, '
                            'no declaradas; lo de la autora sigue en sus archivos.'),
            'entrada': 'matriz/superficie/ (lexico.json, pasajes.json, perfil.json)',
            'pasajes': n_pas,
            'pasajes_por_lengua': dict(por_lengua.most_common()),
            'lenguas_leidas': ['es'],
            'obras': N_OBRAS,
            'vocabulario': len(vocab),
            'asociaciones': len(aristas),
            'parametros': {
                'min_obras': MIN_OBRAS, 'max_fraccion_obras': MAX_FRACCION_OBRAS,
                'min_par_pasajes': MIN_PAR_PASAJES, 'min_par_obras': MIN_PAR_OBRAS,
                'npmi_minimo': NPMI_MINIMO, 'vecinos': VECINOS, 'tam': [TAM_MIN, TAM_MAX],
                'azar_vueltas': AZAR_VUELTAS, 'azar_minimo': AZAR_MINIMO,
                'relaciones_max': RELACIONES_MAX,
            },
            'categorias': len(categorias),
            'relaciones': len(relaciones),
            'relaciones_que_la_autora_no_tendio': lineas,
        },
        'origenes': {
            'autora': 'declarado por la autora: diagonales y emergentes (acciones.json, '
                      'diagonales.json), instrumentos (instrumentos.json, estatuto autor) y '
                      'decisiones sobre propuestas (decisiones.json)',
            'matriz:instrumentos': 'derivado por la matriz desde los perfiles de los instrumentos '
                                   'de la autora (propuestas.json): propone, no decide',
            'matriz:corpus': 'derivado por la matriz solo del corpus, sin listas de la autora '
                             '(este archivo)',
            'lector': 'derivado del recorrido de los visitantes; todavía sin datos (la semilla es '
                      'la huella colectiva, pares [de, a] anónimos)',
        },
        'obras': {o: {'titulo': (obras_info.get(o) or {}).get('titulo') or o, 'taller': taller[o]}
                  for o in todas_obras},
        'categorias': categorias,
        'relaciones': relaciones,
    }
    guardar_json(SALIDA, salida)
    print('autonoma.json: %d categorías, %d relaciones entre obras (%d que la autora no tendió), '
          'vocabulario %d, asociaciones %d' % (len(categorias), len(relaciones), lineas, len(vocab), len(aristas)))


if __name__ == '__main__':
    main()
