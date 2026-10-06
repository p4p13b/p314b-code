"""
comun.py — piezas compartidas por los scripts de la matriz relacional.

Rutas, lectura/escritura de JSON, normalización de texto, ventanas de texto
y los backends de embeddings (enchufables, ver PROPUESTA-MATRIZ.md §9.4).
"""
import hashlib
import json
import html
import os
import time
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from util import cargar_json, leer, slugify  # noqa: E402,F401
from util import guardar_json as _guardar_json  # noqa: E402

# Consola Windows no-UTF-8: ver recalcular_subgrafo.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

MATRIZ_DIR = os.path.dirname(os.path.abspath(__file__))
SITIO_DIR = os.path.dirname(MATRIZ_DIR)
RAIZ_DIR = os.path.dirname(SITIO_DIR)
CACHE_DIR = os.path.join(RAIZ_DIR, 'cache-matriz')
DATOS_LEE_TXT = os.path.join(RAIZ_DIR, 'datos-lee', 'txt')

CONFIG_PATH = os.path.join(MATRIZ_DIR, 'config.json')
INSTRUMENTOS_PATH = os.path.join(MATRIZ_DIR, 'instrumentos.json')
PROPUESTAS_PATH = os.path.join(MATRIZ_DIR, 'propuestas.json')
DECISIONES_PATH = os.path.join(MATRIZ_DIR, 'decisiones.json')
RECORRIDOS_PATH = os.path.join(MATRIZ_DIR, 'recorridos.json')
PASAJES_PATH = os.path.join(CACHE_DIR, 'pasajes.json')

ACCIONES_PATH = os.path.join(SITIO_DIR, 'acciones.json')
CORPUS_PATH = os.path.join(SITIO_DIR, 'corpus.json')
SUBGRAFO_PATH = os.path.join(SITIO_DIR, 'subgrafo.json')
MANIFEST_PATH = os.path.join(SITIO_DIR, 'Archivo', 'manifest.json')


def guardar_json(path, data):
    _guardar_json(path, data, crear_carpeta=True)


def cargar_config():
    return cargar_json(CONFIG_PATH, {})


def clave_obra(titulo):
    """Clave para reconocer la misma obra en un PDF y en un post."""
    t = re.sub(r'\.(docx\.)?pdf$', '', titulo or '', flags=re.I)
    t = re.sub(r'^\s*([IVX]+|\d+)\s*-\s*', '', t)
    return slugify(t)


# ── Texto ──

def normalizar(texto):
    t = unicodedata.normalize('NFC', texto or '')
    t = t.replace('­', '').replace('\xa0', ' ')
    t = re.sub(r'(\w)-\n(\w)', r'\1\2', t)
    return re.sub(r'\s+', ' ', t).strip()


STOPWORDS = set("""
a al algo algun alguna algunas alguno algunos alla alli ambos ante antes aquel aquella aquellas aquello aquellos
aqui asi aun aunque bajo bien cada casi como con contra cual cuales cualquier cuando cuanto de del desde donde dos
el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estaba estado estan estar este esto estos
fue fuera fueron ha haber habia han hasta hay la las le les lo los mas me mi mis mismo mucho muy nada ni no nos
nosotros nuestra nuestro o os otra otras otro otros para pero poco por porque que quien quienes se sea segun ser
si sido siempre sin sino sobre solo son su sus tal tambien tan tanto te tener tiene tienen toda todas todo todos
tu tus un una unas uno unos usted ustedes va vez vos y ya yo
the of and to in is it that for on as with was be by this are or not an at from but his her he she they we you
i my me your their its which who whom were has have had been will would can could there what so if no do does
""".split())


def palabras(texto):
    return re.findall(r'\w+', (texto or '').lower())


def sin_tilde(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn')


def raiz(w):
    """Raíz tosca: primeras 5 letras sin tilde. Sirve para tratar como la
    misma palabra a 'indiferir' e 'indiferencia' al medir coincidencia
    léxica — más estricto que comparar la palabra exacta."""
    w = sin_tilde(w)
    return w[:5] if len(w) > 5 else w


# ── Lemas de instrumentos ──
# "familia" junta las palabras de una misma raíz sacando la terminación
# derivativa o flexiva más larga: indiferir, indiferencia, indiferente e
# indiferido dan "indifer"; instrumento e instrumental, "instrument". Es
# una aproximación sin diccionario: el lema lo confirma la autora en el
# taller. La misma lista está en uploader-v1.html (familiaPalabra), y
# tienen que coincidir.
SUFIJOS_FAMILIA = sorted([
    'amientos', 'imientos', 'amiento', 'imiento', 'aciones', 'iciones', 'idades', 'encias', 'ancias',
    'adoras', 'adores', 'acion', 'icion', 'encia', 'ancia', 'mente', 'idad', 'ibles', 'ables', 'istas',
    'ismos', 'antes', 'entes', 'adora', 'ador', 'ible', 'able', 'ista', 'ismo', 'ante', 'ente', 'ivos',
    'ivas', 'ales', 'ados', 'adas', 'idos', 'idas', 'ando', 'iendo', 'ivo', 'iva', 'ado', 'ada', 'ido',
    'ida', 'al', 'ar', 'er', 'ir', 'es', 'as', 'os', 'a', 'o', 'e', 's',
], key=len, reverse=True)
PALABRAS_VACIAS_LEMA = {'de', 'del', 'la', 'el', 'los', 'las', 'y', 'o', 'en', 'un', 'una', 'por', 'con',
                        'para', 'que', 'al', 'lo', 'su', 'sus', 'como', 'sin', 'entre'}


def familia(palabra):
    w = re.sub(r'[^a-zñ]', '', sin_tilde((palabra or '').lower()))
    for suf in SUFIJOS_FAMILIA:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def misma_familia(a, b):
    if not a or not b:
        return False
    corta, larga = sorted((a, b), key=len)
    return corta == larga or (len(corta) >= 6 and larga.startswith(corta))


def palabra_cabeza(etiqueta):
    """Primera palabra con contenido de una etiqueta ("Indiferir
    instrumental" -> "indiferir")."""
    for w in re.findall(r'[\wñÑáéíóúüÁÉÍÓÚÜ]+', (etiqueta or '').replace('-', ' ')):
        if len(w) >= 3 and sin_tilde(w.lower()) not in PALABRAS_VACIAS_LEMA and not w.isdigit():
            return w.lower()
    return (etiqueta or '').strip().lower()


def lema_propuesto(etiqueta, instrumentos=()):
    """Lema para un instrumento nuevo: el de un instrumento existente de la
    misma familia, si hay; si no, la palabra cabeza de la etiqueta."""
    cabeza = palabra_cabeza(etiqueta)
    fam = familia(cabeza)
    for ins in instrumentos:
        lema = ins.get('lema') or palabra_cabeza(ins.get('etiqueta') or ins.get('id'))
        if misma_familia(fam, familia(lema)):
            return lema
    return cabeza


def palabras_contenido(texto):
    return [w for w in palabras(texto) if len(w) >= 3 and sin_tilde(w) not in STOPWORDS and not w.isdigit()]


def raices_contenido(texto):
    return {raiz(w) for w in palabras_contenido(texto)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def enmascarar(texto, raices):
    """Borra del texto las palabras de contenido cuya raíz esté en raices."""
    def reemplazo(m):
        w = m.group(0)
        if len(w) >= 3 and sin_tilde(w.lower()) not in STOPWORDS and raiz(w.lower()) in raices:
            return ''
        return w
    return re.sub(r'\w+', reemplazo, texto)


def ventanas(texto, largo=40, paso=20):
    """Ventanas de ~largo palabras, como subcadenas exactas del texto."""
    spans = [m.span() for m in re.finditer(r'\S+', texto)]
    if not spans:
        return []
    if len(spans) <= largo:
        return [texto]
    out = []
    for i in range(0, len(spans), paso):
        j = min(i + largo, len(spans))
        out.append(texto[spans[i][0]:spans[j - 1][1]])
        if j == len(spans):
            break
    return out


def trozos(texto, objetivo=50):
    """Parte un texto largo (un emergente) en trozos de ~objetivo palabras,
    cortando en fin de oración cuando se puede. No cambia las palabras: cada
    trozo es una subcadena del texto con los espacios normalizados. Los
    trozos solo se usan para comparar; el emergente no se toca."""
    oraciones = re.split(r'(?<=[.!?;:])\s+', normalizar(texto))
    out, actual = [], []
    for o in oraciones:
        actual.append(o)
        if sum(len(x.split()) for x in actual) >= objetivo:
            out.append(' '.join(actual))
            actual = []
    if actual:
        if out and sum(len(x.split()) for x in actual) < objetivo / 3:
            out[-1] = out[-1] + ' ' + ' '.join(actual)
        else:
            out.append(' '.join(actual))
    grandes = []
    for t in out:
        grandes.extend(ventanas(t, largo=80, paso=60) if len(t.split()) > 100 else [t])
    return grandes


def huella(texto):
    return hashlib.sha1(texto.encode('utf-8')).hexdigest()[:16]


# ── Backends de embeddings ──

def requerir(modulo, como):
    """Importa un módulo opcional; si falta, corta con instrucciones."""
    import importlib
    try:
        return importlib.import_module(modulo)
    except ImportError:
        raise SystemExit('Falta el paquete "%s". %s\nVer sitio/matriz/LEEME.md.' % (modulo, como))


class BackendHash:
    """Trivial: n-gramas de caracteres hasheados. Es léxico por
    construcción; sirve solo para probar que el pipeline corre."""
    nombre = 'hash'

    def __init__(self, dim=512):
        self.dim = dim

    def vectores(self, textos):
        np = requerir('numpy', 'Instalalo con: pip install numpy')
        m = np.zeros((len(textos), self.dim), dtype='float32')
        for i, t in enumerate(textos):
            t = ' ' + ' '.join(palabras_contenido(t)) + ' '
            for n in (3, 4, 5):
                for k in range(len(t) - n + 1):
                    h = int(hashlib.md5(t[k:k + n].encode('utf-8')).hexdigest()[:8], 16)
                    m[i, h % self.dim] += 1.0
        return _normalizar_filas(m)


class BackendSpacy:
    """Sustituto semántico: promedio de vectores de palabras de contenido
    (es_core_news_lg, 500 mil vectores). No es un codificador de oraciones:
    es lo mejor que se puede bajar en una máquina sin acceso a Hugging Face."""
    nombre = 'spacy-es-lg'

    def __init__(self, modelo='es_core_news_lg'):
        spacy = requerir('spacy', 'Instalalo con: pip install spacy && python -m spacy download es_core_news_lg')
        try:
            self.nlp = spacy.load(modelo, exclude=['parser', 'ner', 'morphologizer', 'attribute_ruler', 'lemmatizer', 'tok2vec', 'senter'])
        except OSError:
            raise SystemExit('Falta el modelo de spaCy "%s". Bajalo con: python -m spacy download %s' % (modelo, modelo))
        self.modelo = modelo

    def vectores(self, textos):
        np = requerir('numpy', 'Instalalo con: pip install numpy')
        dim = self.nlp.vocab.vectors.shape[1]
        m = np.zeros((len(textos), dim), dtype='float32')
        for i, doc in enumerate(self.nlp.tokenizer.pipe(textos, batch_size=512)):
            vs = [t.vector for t in doc if t.has_vector and t.is_alpha and not t.is_stop and len(t) >= 3]
            if vs:
                m[i] = np.mean(vs, axis=0)
        return _normalizar_filas(m)


class BackendSentenceTransformers:
    """El backend real: un modelo multilingüe de sentence-transformers que
    corre local. Se baja una vez de Hugging Face (en tu máquina)."""
    nombre = 'sentence-transformers'

    def __init__(self, modelo='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'):
        st = requerir('sentence_transformers', 'Instalalo con: pip install sentence-transformers '
                      '(la primera vez baja el modelo de Hugging Face, ~500 MB). '
                      'Sin eso, podés probar con --backend spacy-es-lg.')
        self.modelo = modelo
        self.m = st.SentenceTransformer(modelo)

    def vectores(self, textos):
        return self.m.encode(textos, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype('float32')


def _normalizar_filas(m):
    np = requerir('numpy', 'Instalalo con: pip install numpy')
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def backend_desde(nombre, modelo=None):
    if nombre == 'hash':
        return BackendHash()
    if nombre == 'spacy-es-lg':
        return BackendSpacy(modelo or 'es_core_news_lg')
    if nombre == 'sentence-transformers':
        return BackendSentenceTransformers(modelo) if modelo else BackendSentenceTransformers()
    raise SystemExit('Backend desconocido: %s (hash | spacy-es-lg | sentence-transformers)' % nombre)


class CacheVectores:
    """Vectores por huella de texto, un archivo por backend+modelo, en
    cache-matriz/ (fuera de sitio/, ignorado por git)."""

    def __init__(self, backend):
        np = requerir('numpy', 'Instalalo con: pip install numpy')
        self.np = np
        self.backend = backend
        etiqueta = slugify(backend.nombre + '-' + getattr(backend, 'modelo', ''))
        self.path = os.path.join(CACHE_DIR, 'vectores-%s.npz' % etiqueta)
        self.tabla = {}
        if os.path.exists(self.path):
            d = np.load(self.path, allow_pickle=False)
            for k, v in zip(d['claves'], d['matriz']):
                self.tabla[str(k)] = v

    def vectores(self, textos):
        faltan = [t for t in dict.fromkeys(textos) if huella(t) not in self.tabla]
        if len(faltan) > 2048:
            print('  vectores: %d por calcular (%d ya en caché)' % (len(faltan), len(textos) - len(faltan)), flush=True)
        ultimo = time.time()
        for i in range(0, len(faltan), 2048):
            lote = faltan[i:i + 2048]
            for t, v in zip(lote, self.backend.vectores(lote)):
                self.tabla[huella(t)] = v
            # Guardado parcial cada pocos minutos: si la corrida se corta
            # (p. ej. por el límite de tiempo de Actions), la próxima sigue
            # desde acá en vez de empezar de cero.
            if time.time() - ultimo > 240:
                self.guardar(); ultimo = time.time()
                print('  vectores: %d de %d, guardados' % (min(i + 2048, len(faltan)), len(faltan)), flush=True)
        return self.np.array([self.tabla[huella(t)] for t in textos], dtype='float32')

    def guardar(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        claves = list(self.tabla.keys())
        self.np.savez(self.path, claves=self.np.array(claves), matriz=self.np.array([self.tabla[k] for k in claves], dtype='float32'))


# ── Corpus ──

def diagonales_confirmadas(acciones=None):
    """Diagonales de acciones.json (estatuto autor), con su origen.

    - Una diagonal se guarda en sus dos puntas (ida y vuelta, la vuelta con
      «reciproca_de»): acá cuenta una sola vez.
    - Sin instrumento, su significante es el título: la autora tiende la
      diagonal y le pone de título lo que relaciona las dos anclas. Dos
      diagonales con el mismo título son el mismo concepto.
    - «texto_perfil» es con lo que el motor arma el perfil: el emergente o,
      si no hay, el título, la sinopsis y los párrafos de las dos anclas.
    - Un ancla de diagonal vacía («vacia») fija la relación sin nombrarla:
      aunque tenga título, no se vuelve instrumento."""
    acciones = acciones if acciones is not None else cargar_json(ACCIONES_PATH, {'acciones': {}})
    todas = acciones.get('acciones') or {}
    out = []
    for aid, a in todas.items():
        origen = a.get('origen') or {}
        for t in a.get('tipos') or []:
            if t.get('tipo') != 'diagonal' or t.get('reciproca_de'):
                continue
            t = dict(t)
            titulo = (t.get('titulo') or '').strip()
            if not t.get('instrumento') and titulo and not t.get('vacia'):
                t['instrumento'] = slugify(titulo)
                t['instrumento_nuevo_label'] = t.get('instrumento_nuevo_label') or titulo
                t['significante'] = True
            texto = (t.get('emergente') or '').strip()
            if not texto:
                resumen = (t.get('resumen') or '').strip()
                partes = [titulo, resumen if resumen.lower() != titulo.lower() else '',
                          parrafo_de_accion(aid, todas), parrafo_de_accion(t.get('destino'), todas)]
                texto = ' '.join(p for p in partes if p)
            out.append({'id': aid, 'origen': origen, 'tipo': t, 'texto_perfil': texto})
    return out


_OBRAS_CACHE = {}


def parrafo_de_accion(aid, todas):
    """El párrafo (texto plano) donde está la marca de una acción, leído del
    .json de su obra. Si no se encuentra, el fragmento anclado."""
    a = todas.get(aid or '') or {}
    origen = a.get('origen') or {}
    frag = ' '.join((origen.get('fragmento') or '').split())
    obra = origen.get('obra')
    if not obra:
        return frag
    if obra not in _OBRAS_CACHE:
        _OBRAS_CACHE[obra] = cargar_json(os.path.join(SITIO_DIR, 'obras', obra + '.json'), {}) or {}
    for ch in _OBRAS_CACHE[obra].get('chapters') or []:
        body = ch.get('body') or ''
        if aid not in body:
            continue
        for bloque in re.split(r'</p>|</h\d>|<br\s*/?>|</div>|</blockquote>', body):
            if aid in bloque:
                texto = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', bloque)).split())
                # un párrafo muy largo se recorta alrededor del fragmento
                if len(texto) > 1500:
                    i = max(0, texto.find(frag[:40]) if frag else 0)
                    texto = texto[max(0, i - 600):i + len(frag) + 600]
                return texto
    return frag


def resolver_instrumento(iid, registro):
    """Devuelve el id canónico del registro para un id o alias."""
    if not iid:
        return None
    for ins in (registro.get('instrumentos') or []):
        if ins['id'] == iid or iid in (ins.get('alias') or []):
            return ins['id']
    return iid
