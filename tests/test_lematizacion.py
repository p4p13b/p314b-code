#!/usr/bin/env python3
"""Las tres lematizaciones dan lo mismo: matriz/anexo/scripts/lematica.py,
diagonal.js y matriz-superficie.js (las dos de JS, con Node).

Compara la clave de cada palabra de una muestra fija del cuerpo (formas del
diccionario, formas de lemas.json, palabras que el diccionario no conoce y
casos conocidos). Uso, desde la raíz: python3 tests/test_lematizacion.py
"""
import json
import os
import random
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITIO = os.path.join(RAIZ, 'sitio')
sys.path.insert(0, os.path.join(SITIO, 'matriz', 'anexo', 'scripts'))
from lematica import clave, norm, F, AUTO  # noqa: E402  (cambia de carpeta: usar rutas absolutas)

CASOS = ('historia historias memoria presencia indiferencia indiferente indiferentes indiferir indiferido '
         'madres narradas narrando narración propias mismas buenas sería seria escribía tenía días canta '
         'cantamos es tiene dice sí mismidades dioses instante existente distinguimos distinguir '
         'mismizacion nadiedad decirse hacerse resultados resultado constructor tostring valueof').split()

NODE = r"""
const fs = require('fs'), vm = require('vm');
const [sitio, palabrasRuta] = process.argv.slice(1);
const leer = r => JSON.parse(fs.readFileSync(sitio + '/' + r, 'utf8'));
const L = leer('lemas.json'), A = fs.existsSync(sitio + '/lemas-auto.json') ? leer('lemas-auto.json') : {};
const palabras = JSON.parse(fs.readFileSync(palabrasRuta, 'utf8'));
function bloque(archivo, desde, hasta) {
  const s = fs.readFileSync(sitio + '/' + archivo, 'utf8');
  const i = s.indexOf(desde), j = s.indexOf(hasta, i);
  if (i < 0 || j < 0) throw new Error(archivo + ': no encuentro el bloque de lematización');
  return s.slice(i, j);
}
// diagonal.js: lemasArchivo() lee con fetch; acá, de disco.
const ctxD = { BASE: '', fetch: r => Promise.resolve({ ok: fs.existsSync(sitio + '/' + r), json: () => Promise.resolve(leer(r)) }) };
vm.runInNewContext(bloque('diagonal.js', '// ── lemas en común', 'function marcarComunes') + ';this.lemasArchivo = lemasArchivo; this.clave = clave;', ctxD);
const ctxS = {};
vm.runInNewContext('let AUTO, LEMAS_AUTO, F, LEMAS_DEF, IGN; const norm = w => w.toLowerCase().normalize("NFD").replace(/\\p{M}/gu, "");'
  + bloque('matriz-superficie.js', '/* ── lematización', 'function cuenta(') + ';this.prepararLemas = prepararLemas; this.clave = clave;', ctxS);
ctxS.prepararLemas(L, A);
ctxD.lemasArchivo().then(LD => {
  const out = {};
  palabras.forEach(w => { out[w] = [ctxD.clave(w, LD), ctxS.clave(w)]; });
  process.stdout.write(JSON.stringify(out));
});
"""


def muestra():
    rnd = random.Random(314)
    auto = sorted(AUTO)
    propias = sorted(F)
    desconocidas = []
    txt = os.path.join(RAIZ, 'datos-lee', 'txt')
    for base, _, archivos in sorted(os.walk(txt)):
        for a in sorted(archivos)[:3]:
            with open(os.path.join(base, a), encoding='utf-8', errors='ignore') as fh:
                desconocidas += [w for w in fh.read().split() if w.isalpha() and len(w) >= 3 and w.lower() not in AUTO][:200]
    ps = CASOS + rnd.sample(auto, min(3000, len(auto))) + rnd.sample(propias, min(1000, len(propias))) + desconocidas[:2000]
    return sorted(set(ps))


def main():
    palabras = muestra()
    ruta = os.path.join(RAIZ, 'cache-matriz', 'test-lemas.json')
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(palabras, fh, ensure_ascii=False)
    js = json.loads(subprocess.run(['node', '-e', NODE, SITIO, ruta], check=True, capture_output=True, text=True).stdout)
    malas = []
    for w in palabras:
        py = clave(w)
        d, s = js[w]
        if d != py or s != (py if py == 'sí' else norm(py)):
            malas.append((w, py, d, s))
    for m in malas[:30]:
        print('  %-20s python=%-16s diagonal.js=%-16s superficie=%s' % m)
    print('%d palabras, %d diferencias' % (len(palabras), len(malas)))
    sys.exit(1 if malas else 0)


if __name__ == '__main__':
    main()
