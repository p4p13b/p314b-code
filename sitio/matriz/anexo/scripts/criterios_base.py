"""Funciones de los criterios intrínsecos (las usan criterios.py y calibrar.py).

Criterios intrínsecos tomados de las últimas obras (VI-0 y ensayos),
aplicados a todas las obras.

1. IIN — no teoría, C.2: TTR, TTRinst, Eg, Ef, Esint, DRI e Índice de
   Inconsistencia Necesaria. Operacionalización calibrada sobre C.1 (el
   texto que C.2 mide): TTR 0.354 (0.36), TTRinst 0.65 (0.72), Vg 19 (25),
   Vf 23 (27), Vc 71 (68), DRI 0.019 (0.02). Ventana = largo de C.1.
2. cq — no teoría, ci:Q: curvatura del quantum = cortes efectuados /
   cortes posibles (0 = continuo indiferenciado; →1 = toda diferencia
   se vuelve mismidad).
3. Costo de integración — sí, «Validez y valor»: parte del texto fuera del
   estándar endógeno del campo (lemas presentes en ≥ la mitad de las obras).
4. Hiperespecificidad — no teoría / dos puntos: parte del léxico que solo
   existe en esa obra.
5. Al-menos-dos — almenos: balance entre enunciación plural (nosotros) y
   singular (yo).
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, html, collections, statistics, math, sys
from lematica import clave, cuenta, norm, VACIAS, EXTRA

P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
META = P['meta']['sitios']
VENT = 1946
FUN = set('que de la el en y a los se no ni lo las un una por con su del al es o como más mas pero si sin para ya le me te nos tu mi'.split())
VOC = 'aeiou'
# el espacio como grafema positivo (dos puntos, 2.2): hueco de 3+ espacios dentro de la línea
HUECO = re.compile(r'(?<=\S) {3,}(?=\S)')


def sin_tilde(w):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn')


def texto_pdf(ruta):
    t = open(RAIZ + ruta, encoding='utf-8', errors='replace').read()
    t = re.sub(r'^\[.*?\]\s*', '', t)
    t = re.sub(r'<<<PAGE \d+>>>', '\n\n', t)
    return t


def texto_post(ruta):
    d = json.load(open(RAIZ + ruta))
    partes = []
    for ch in d.get('chapters', []):
        b = ch.get('body') or ''
        b = re.sub(r'(?i)<br\s*/?>', '\n', b)
        b = re.sub(r'(?i)</(p|div|h\d|li|blockquote)>', '\n\n', b)
        b = re.sub(r'<[^>]+>', '', b)
        partes.append(html.unescape(b))
    return '\n\n'.join(partes)


def cortes_de_linea(t):
    """Saltos de línea que son corte (verso, línea corta), no ajuste de
    maquetación: la línea termina antes del margen de esa obra."""
    lineas = [l.rstrip() for l in t.split('\n')]
    largos = sorted(len(l) for l in lineas if l.strip())
    if not largos:
        return set()
    p90 = largos[int(len(largos) * 0.9) - 1] if len(largos) > 10 else max(largos)
    pos, res = 0, set()
    for l in lineas:
        fin = pos + len(l)
        if l.strip() and len(l.strip()) < 0.7 * p90 and not re.search(r'[.,;:!?…–—-]\s*$', l):
            res.add(fin)
        pos = fin + 1
    return res


def rima_asonante(w):
    w = sin_tilde(w.lower())
    idx = [i for i, c in enumerate(w) if c in VOC]
    if not idx:
        return None
    i = idx[-2] if len(idx) >= 2 and w[-1] in VOC + 'ns' else idx[-1]
    return ''.join(c for c in w[i:] if c in VOC)


def medir_ventana(t, detalle=False):
    W = [(m.group().lower(), m.start(), m.end()) for m in re.finditer(r"[^\W\d_]+", t)]
    toks = [w for w, _, _ in W]
    T = len(toks)
    if T < 200:
        return None
    Vstd = len(set(toks))
    L = ['<s>'] + toks[:-1]; R = toks[1:] + ['</s>']
    Vinst = len({(l if l in FUN else '*', w, r if r in FUN else '*') for l, w, r in zip(L, toks, R)})
    marcas = set()
    for mm in re.finditer(r"[^\w\s]+", t):
        s, e = mm.span()
        a = t[s - 1] if s > 0 else ' '
        b = t[e] if e < len(t) else ' '
        marcas.add((mm.group(), a.isspace(), b.isspace()))
    Vg = len(marcas) + (1 if re.search(r'\n\s*\n', t) else 0) + (1 if re.search(r'[^\n]\n[^\n]', t) else 0) + (1 if HUECO.search(t) else 0)
    finales = [m.group(1) for m in re.finditer(r"([^\W\d_]+)\s*(?:[.,;:!?¡¿…–—-]|\n)", t)]
    Vf = len({r for r in (rima_asonante(w) for w in finales) if r})
    lem = collections.Counter(norm(clave(w)) for w in re.findall(r"[^\W\d_]+", t) if cuenta(w))
    Vc = sum(1 for v in lem.values() if v >= 3)
    rep = sum(1 for i, w in enumerate(toks) if w in toks[max(0, i - 2):i])
    if detalle:
        return {'T': T, 'V': Vstd, 'Vinst': Vinst, 'Vg': Vg, 'Vf': Vf, 'Vc': Vc, 'repeticiones': rep,
                'TTR': Vstd / T, 'TTRinst': Vinst / T, 'Eg': Vg / T, 'Ef': Vf / T, 'Esint': Vc / T, 'DRI': rep / T,
                'IIN': Vinst * Vinst / ((Vc + Vg + Vf) * T)}
    return {'T': T, 'TTR': Vstd / T, 'TTRinst': Vinst / T, 'Eg': Vg / T, 'Ef': Vf / T, 'Esint': Vc / T, 'DRI': rep / T,
            'IIN': Vinst * Vinst / ((Vc + Vg + Vf) * T)}


def ventanas(t):
    pos = [m.start() for m in re.finditer(r"[^\W\d_]+", t)]
    res = []
    for i in range(0, len(pos), VENT):
        a = pos[i]
        b = pos[i + VENT] if i + VENT < len(pos) else len(t)
        if len(pos) - i < VENT * 0.5 and res:
            break
        res.append((a, b))
    return res


EN = set('the and of to is that it you he she was for with as his her are this be at by not or have from but they we'.split())


def idioma(t):
    w = re.findall(r"[a-z]+", t.lower()[:200000])
    en = sum(1 for x in w if x in EN)
    return 'en' if en / max(1, len(w)) > 0.12 else 'es'


PL_ES = re.compile(r"\b(nosotros|nosotras|nuestro|nuestra|nuestros|nuestras|nos)\b", re.I)
SG_ES = re.compile(r"\b(yo|me|mí|mi|mis|conmigo|mío|mía|míos|mías)\b", re.I)
PL_EN = re.compile(r"\b(we|us|our|ours|ourselves)\b", re.I)
SG_EN = re.compile(r"\b(i|me|my|mine|myself)\b")

# Las últimas obras: la serie VI - +0, según la cronología de la autora
# (fechas.py). De repetir es de «entre No y +0» y Términos y condiciones
# es de 2023 (IV - Póstumos).
from fechas import ULTIMAS  # noqa: E402,F401
