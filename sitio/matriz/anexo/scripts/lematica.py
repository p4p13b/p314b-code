"""Mapa lemático de los significantes pesados y desplazamiento a otras obras.

Lematiza igual que diagonal.js y matriz-superficie.js: lemas.json (lo que
decidió la autora, manda), los irregulares, lemas-auto.json (el diccionario,
lo arma sitio/lemas_auto.py) y, para lo que el diccionario no conoce, las
reglas generales. Así «indiferir» e «indiferencia» siguen siendo lemas
distintos. tests/test_lematizacion.py comprueba que las tres dan lo mismo.
"""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, unicodedata, collections, math, pickle, sys

L = json.load(open(RAIZ + 'sitio/lemas.json'))
F = {k.lower(): v for k, v in (L.get('formas') or {}).items()}
LEMAS_DEF = {v.lower() for v in F.values()}
IGN = {x for x in (L.get('ignorar') or [])}


def norm(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w.lower()) if unicodedata.category(c) != 'Mn')


# Lemas del diccionario (sitio/lemas_auto.py). Sin el archivo, solo reglas.
try:
    _A = json.load(open(RAIZ + 'sitio/lemas-auto.json'))
except (OSError, ValueError):
    _A = {}
AUTO = {w: w for w in (_A.get('propias') or [])}
AUTO.update(_A.get('formas') or {})
LEMAS_AUTO = {norm(v) for v in AUTO.values()}


VACIAS = set(norm(w) for w in ('que como para pero porque sino aunque cuando donde entre sobre desde hasta este esta esto estos estas ese esa eso esos esas aquel aquella sólo solo tanto tan más menos muy también ella ellos ellas nuestro nuestra nuestros nuestras decir dicho hacer sido será sean siendo cual cuales quien quienes todo toda todos todas otro otra otros otras nada algo cada mismo misma ante bajo tras '
    'el la lo los las un una unos unas de del al en y e o u a con por sin se su sus le les me te nos os mi tu es son fue era ser hay ha han he no ni si ya así asi aquí acá ahí allí cuyo cuya').split())
# Para el mapa, «mismo/misma», «nada» y «otro» NO son vacías: son significantes.
VACIAS -= {'mismo', 'misma', 'nada', 'otro', 'otra', 'otros', 'otras'}
# Vacías extra solo para el análisis (función, no concepto).
EXTRA = set(norm(w) for w in ('pues luego entonces aun aún ello esto sus lo cual donde mientras tal tales cuanto cuanta cuantos unos mas sí_no vez veces sea puede pueden poder tener estar haber hab ser hacer decir modo forma manera caso parte cosa ver dar ir voy va van vez tiempo hoy aqui alli cada casi bien mal mucho mucha muchos muchas poco poca pocos pocas siempre nunca ahora antes despues después solamente sólo aun asimismo acaso quizás quizas través traves según segun dentro fuera frente hacia contra durante mediante the and of to in is that it for you he she was on with as his her are be this at by not or have from but they we an which one all my me your their so no if would what there out when up been who them said more has will do can into could than its just like other only then some these time any our about him how well'.split()))

IRREG = dict(es='ser', son='ser', era='ser', eran='ser', fue='ser', fueron='ser', sea='ser', sean='ser', siendo='ser', sido='ser', sera='ser', soy='ser', somos='ser', seria='ser',
             esta='estar', estan='estar', estaba='estar', estando='estar', estamos='estar',
             tiene='tener', tienen='tener', tenia='tener', tenga='tener', tuvo='tener',
             hace='hacer', hacen='hacer', hizo='hacer', hecho='hacer', haciendo='hacer',
             dice='decir', dicen='decir', dijo='decir', diciendo='decir', decimos='decir', diriamos='decir', deciamos='decir',
             puede='poder', pueden='poder', podia='poder', pudo='poder', podemos='poder', podria='poder', podriamos='poder')
REGLAS = [(r'ciones$', 'cion'), (r'siones$', 'sion'), (r'idades$', 'idad'), (r'ces$', 'z'),
          (r'iendo$', 'er'), (r'ando$', 'ar'), (r'(ados|adas|ado|ada)$', 'ar'), (r'(idos|idas|ido|ida)$', 'er'),
          (r'(abamos|aban|abas|aba)$', 'ar'), (r'(iamos|ian)$', 'er'), (r'(aron|amos)$', 'ar'), (r'(ieron|emos|imos)$', 'er'),
          (r'ones$', 'on'), (r'([^aeiou])es$', r'\1'), (r'([aeiou])s$', r'\1')]


def lema(w):
    bajo = w.lower()
    if bajo == 'sí':
        return 'sí'
    dado = F.get(bajo) or F.get(norm(bajo))
    if dado:
        return 'sí' if dado == 'sí' else norm(dado)
    n = norm(w)
    if n in IRREG:
        return IRREG[n]
    auto = AUTO.get(bajo)
    if auto:
        dado = F.get(auto) or F.get(norm(auto))
        return norm(dado or auto)
    if len(n) > 7:
        n = re.sub(r'mente$', '', n)
    for rx, rep in REGLAS:
        if re.search(rx, n):
            n = re.sub(rx, rep, n, count=1)
            break
    return n


def clave(w):
    l = lema(w)
    bajo = w.lower()
    if l == 'sí' or bajo in F or norm(w) in F:
        return l
    if bajo in LEMAS_DEF:
        return bajo
    # lo que viene del diccionario (o cae en uno de sus lemas) va tal cual
    if bajo in AUTO or l in LEMAS_AUTO:
        return l
    c = re.sub(r'(ar|er|ir)$', '', l)
    return c if len(c) >= 4 else l


TOKEN = re.compile(r'[^\W\d_][^\W\d_\-]+', re.U)


def cuenta(w):
    if w.lower() == 'sí':
        return True
    n = norm(w)
    return len(w) >= 3 and n not in VACIAS and n not in EXTRA and w not in IGN


def tokens(txt):
    """[(forma, clave)] de las palabras que cuentan."""
    return [(w.lower(), clave(w)) for w in TOKEN.findall(txt) if cuenta(w)]


if __name__ == '__main__':
    P = json.load(open(RAIZ + 'cache-matriz/pasajes.json'))
    meta = P['meta']['sitios']
    pas = P['pasajes']
    docs = []
    formas_de = collections.defaultdict(collections.Counter)  # clave -> formas
    from duplicados import ids_fuera
    FUERA_ = ids_fuera()
    for p in pas:
        if p['id'] in FUERA_:
            continue
        tk = tokens(p['texto'])
        for f, c in tk:
            formas_de[c][f] += 1
        docs.append({'id': p['id'], 'obra': p['obra_clave'], 'claves': [c for _, c in tk], 'texto': p['texto']})
    pickle.dump({'docs': docs, 'formas_de': formas_de, 'meta': meta}, open(sys.argv[1], 'wb'))
    print(len(docs), 'pasajes;', len(formas_de), 'claves')
