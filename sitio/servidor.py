#!/usr/bin/env python3
"""
servidor.py

El servidor local del sitio (lo mismo que `python -m http.server 8000`)
más el botón "⚡ publicar" del taller y del índice: corre los scripts de
Python sin abrir otra terminal.

Uso, desde la carpeta sitio/:
    python servidor.py            # http://localhost:8000/
    python servidor.py 8080       # otro puerto

Qué hace cada botón:
  ⚡ publicar (taller)       guarda obras/<slug>.json y corre, en orden:
                            generar_obra.py, recalcular_subgrafo.py,
                            matriz/recalibrar.py,
                            matriz/calcular_recorridos.py y publicar.py
                            (arma web/ con las obras marcadas para la web)
  ⚡ regenerar y publicar    lo mismo sobre todas las obras de obras/*.json
  todo (índice)
  quitar de la web /        eliminar_obra.py (--ocultar o a la papelera)
  eliminar obra (índice)    y después lo mismo que "regenerar y publicar todo"
  ⬆ subir a la web          git add sitio/ web/ + git commit + git push
                            (Cloudflare publica web/ solo al recibir el push)

Solo escucha en 127.0.0.1 (nadie de afuera de tu máquina puede usarlo), y
las llamadas exigen un encabezado propio que una página ajena no puede
mandar sin permiso del servidor (que no lo da).
"""
import base64
import binascii
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SLUG_OK = re.compile(r'^[a-z0-9-]+$')
LAMINA_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.pdf$')
VOZ_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.(mp3|m4a|ogg|oga|opus|wav|webm|aac)$')
PAPELERA_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.json$')
# Scripts que corren antes y después de generar la(s) obra(s): los de
# pasos.py (la misma secuencia que «Publicar sitio»), salvo los que no
# van en local (tender_decisiones, crear_obras_pdf y matriz/cowork, que
# corren en GitHub al publicar).
sys.path.insert(0, HERE)
import pasos  # noqa: E402
SCRIPTS_ANTES = [[s] for s, _, local in pasos.ANTES if local]
SCRIPTS_DESPUES = [[s] for s, _, local in pasos.DESPUES if local]


def correr(args, cwd=HERE):
    """Corre un comando y devuelve (ok, texto con la salida)."""
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env, timeout=600)
    except Exception as e:  # noqa: BLE001 — se informa al taller tal cual
        return False, f'✗ no se pudo correr {" ".join(args)}: {e}\n'
    salida = (p.stdout or '') + (p.stderr or '')
    return p.returncode == 0, salida


todas_las_obras = pasos.todas_las_obras


def pipeline(slugs):
    """generar_obra.py de cada slug + los scripts de después. Corta en el
    primer error (así no se recalcula nada sobre una obra que no se generó)."""
    log = []
    for args in SCRIPTS_ANTES:
        log.append('$ python ' + ' '.join(args))
        ok, out = correr([sys.executable] + args)
        log.append(out.rstrip())
        if not ok:
            return False, '\n'.join(log)
    for slug in slugs:
        log.append(f'$ python generar_obra.py obras/{slug}.json')
        ok, out = correr([sys.executable, 'generar_obra.py', os.path.join('obras', slug + '.json')])
        log.append(out.rstrip())
        if not ok:
            return False, '\n'.join(log)
    for args in SCRIPTS_DESPUES:
        log.append('$ python ' + ' '.join(args))
        ok, out = correr([sys.executable] + args)
        log.append(out.rstrip())
        if not ok:
            return False, '\n'.join(log)
    return True, '\n'.join(log)


def subir():
    ok, out = correr(['git', 'add', 'sitio', 'web'], cwd=REPO)
    log = ['$ git add sitio web\n' + out.rstrip()]
    if not ok:
        return False, '\n'.join(log)
    ok, out = correr(['git', 'diff', '--cached', '--quiet'], cwd=REPO)
    if ok:
        log.append('(no hay cambios para subir en sitio/)')
    else:
        msg = 'Publicar desde el taller (' + datetime.now().strftime('%Y-%m-%d %H:%M') + ')'
        ok, out = correr(['git', 'commit', '-m', msg], cwd=REPO)
        log.append('$ git commit -m "' + msg + '"\n' + out.rstrip())
        if not ok:
            return False, '\n'.join(log)
    ok, out = correr(['git', 'push'], cwd=REPO)
    log.append('$ git push\n' + out.rstrip())
    return ok, '\n'.join(log)


class Manejador(SimpleHTTPRequestHandler):
    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(cuerpo)

    def end_headers(self):
        # Que el navegador no guarde copias viejas de los .json y .html
        # mientras trabajás (el sitio los relee después de publicar).
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_POST(self):
        if not self.path.startswith('/api/'):
            return self._json(404, {'ok': False, 'error': 'no existe'})
        # Protección contra páginas ajenas: el encabezado propio obliga a
        # una consulta previa (CORS) que este servidor nunca aprueba.
        if self.headers.get('X-P314B') != '1':
            return self._json(403, {'ok': False, 'error': 'falta el encabezado X-P314B'})
        host = (self.headers.get('Host') or '').split(':')[0]
        if host not in ('localhost', '127.0.0.1'):
            return self._json(403, {'ok': False, 'error': 'solo desde localhost'})
        try:
            largo = int(self.headers.get('Content-Length') or 0)
            datos = json.loads(self.rfile.read(largo) or b'{}')
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {'ok': False, 'error': 'JSON inválido'})

        accion = self.path[len('/api/'):].strip('/')
        if accion == 'estado':
            return self._json(200, {'ok': True, 'local': True})
        if accion == 'publicar':
            slug = datos.get('slug') or ''
            obra = datos.get('obra')
            if not SLUG_OK.match(slug) or not isinstance(obra, dict):
                return self._json(400, {'ok': False, 'error': 'slug u obra inválidos'})
            destino = os.path.join(HERE, 'obras', slug + '.json')
            with open(destino, 'w', encoding='utf-8') as f:
                json.dump(obra, f, ensure_ascii=False, indent=2)
                f.write('\n')
            ok, log = pipeline([slug])
            return self._json(200, {'ok': ok, 'log': f'✓ guardado obras/{slug}.json\n' + log})
        if accion == 'regenerar':
            ok, log = pipeline(todas_las_obras())
            return self._json(200, {'ok': ok, 'log': log})
        if accion == 'eliminar':
            # una obra (slug) o varias (slugs); se sigue aunque alguna no se pueda
            slugs = datos.get('slugs') or [datos.get('slug') or '']
            if not isinstance(slugs, list) or not slugs or not all(isinstance(x, str) and SLUG_OK.match(x) for x in slugs):
                return self._json(400, {'ok': False, 'error': 'slug inválido'})
            log, hechas = [], 0
            for slug in slugs:
                args = ['eliminar_obra.py', slug] + (['--ocultar'] if datos.get('modo') == 'ocultar' else [])
                ok, out = correr([sys.executable] + args)
                log.append('$ python ' + ' '.join(args) + '\n' + out.rstrip())
                hechas += ok
            if not hechas:
                return self._json(200, {'ok': False, 'log': '\n'.join(log)})
            ok, resto = pipeline(todas_las_obras())
            return self._json(200, {'ok': ok, 'log': '\n'.join(log) + f'\n({hechas}/{len(slugs)} hechas)\n' + resto})
        if accion == 'decisiones':
            if not isinstance(datos.get('decisiones'), list):
                return self._json(400, {'ok': False, 'error': 'decisiones inválidas'})
            with open(os.path.join(HERE, 'matriz', 'decisiones.json'), 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
                f.write('\n')
            return self._json(200, {'ok': True, 'log': f'✓ matriz/decisiones.json: {len(datos["decisiones"])} decisiones'})
        if accion == 'homofonos':
            grupos = datos.get('grupos')
            if not isinstance(grupos, list) or not all(
                    isinstance(g, list) and len(g) >= 2 and all(isinstance(w, str) and 0 < len(w) <= 40 for w in g)
                    for g in grupos):
                return self._json(400, {'ok': False, 'error': 'grupos inválidos'})
            ruta = os.path.join(HERE, 'homofonos.json')
            try:
                with open(ruta, encoding='utf-8') as f:
                    actual = json.load(f)
            except (OSError, json.JSONDecodeError):
                actual = {}
            actual['grupos'] = grupos
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(actual, f, ensure_ascii=False, indent=1)
                f.write('\n')
            return self._json(200, {'ok': True, 'log': f'✓ homofonos.json: {len(grupos)} grupos'})
        if accion == 'diagonales':
            # Lo que la autora carga desde la visualización de una diagonal
            # (nodos, concepto, notas, vínculos, anclas): diagonal.js.
            if not isinstance(datos.get('diagonales'), dict) or not isinstance(datos.get('conceptos'), dict):
                return self._json(400, {'ok': False, 'error': 'diagonales inválidas'})
            with open(os.path.join(HERE, 'diagonales.json'), 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=1)
                f.write('\n')
            return self._json(200, {'ok': True, 'log': f'✓ diagonales.json: {len(datos["diagonales"])} diagonales'})
        if accion == 'mareas':
            # Las mareas de los textos (el botón «marea» del índice): solo
            # reglas con las claves que entiende mareas.js.
            textos = datos.get('textos')
            claves = {'horas', 'dias', 'fechas', 'desde', 'hasta', 'mensaje', 'vuelve'}
            if not isinstance(textos, dict) or not all(
                    isinstance(k, str) and re.match(r'^[a-z0-9_-]{1,120}$', k) and isinstance(v, dict) and set(v) <= claves
                    for k, v in textos.items()):
                return self._json(400, {'ok': False, 'error': 'mareas inválidas'})
            with open(os.path.join(HERE, 'mareas.json'), 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
                f.write('\n')
            return self._json(200, {'ok': True, 'log': f'✓ mareas.json: {len(textos)} regla(s)'})
        if accion == 'guardadas':
            # Para el panel "guardadas" del taller: los .json de obras/ y
            # de papelera/ (solo nombres; se abren con un GET normal).
            def nombres(carpeta):
                d = os.path.join(HERE, carpeta)
                return sorted(f for f in os.listdir(d) if f.endswith('.json')) if os.path.isdir(d) else []
            return self._json(200, {'ok': True, 'obras': nombres('obras'), 'papelera': nombres('papelera')})
        if accion == 'papelera-borrar':
            # Borrar de la papelera lo que la autora eligió en «guardadas»
            # (uno o varios .json). Solo nombres sueltos de papelera/.
            nombres = datos.get('archivos')
            if not isinstance(nombres, list) or not nombres or not all(
                    isinstance(n, str) and PAPELERA_OK.match(n) for n in nombres):
                return self._json(400, {'ok': False, 'error': 'nombres inválidos'})
            log, borrados = [], 0
            for n in nombres:
                ruta = os.path.join(HERE, 'papelera', n)
                if os.path.isfile(ruta):
                    os.remove(ruta)
                    borrados += 1
                    log.append(f'✓ borrado papelera/{n}')
                else:
                    log.append(f'· papelera/{n} ya no estaba')
            return self._json(200, {'ok': True, 'borrados': borrados, 'log': '\n'.join(log)})
        if accion == 'laminas':
            # PDF de las láminas (Archivo/laminas/): se ven solo desde la
            # obra que las usa, no son posteos ni van al índice
            carpeta = os.path.join(HERE, 'Archivo', 'laminas')
            nombres = sorted(f for f in os.listdir(carpeta) if f.lower().endswith('.pdf')) if os.path.isdir(carpeta) else []
            return self._json(200, {'ok': True, 'laminas': nombres})
        if accion == 'lamina':
            nombre = datos.get('nombre') or ''
            if not LAMINA_OK.match(nombre) or not isinstance(datos.get('datos'), str):
                return self._json(400, {'ok': False, 'error': 'nombre o datos inválidos'})
            try:
                crudo = base64.b64decode(datos['datos'], validate=True)
            except (ValueError, binascii.Error):
                return self._json(400, {'ok': False, 'error': 'datos inválidos'})
            if not crudo.startswith(b'%PDF') or len(crudo) > 40 * 1024 * 1024:
                return self._json(400, {'ok': False, 'error': 'no es un PDF (o pasa de 40 MB)'})
            carpeta = os.path.join(HERE, 'Archivo', 'laminas')
            os.makedirs(carpeta, exist_ok=True)
            with open(os.path.join(carpeta, nombre), 'wb') as f:
                f.write(crudo)
            return self._json(200, {'ok': True, 'log': f'✓ Archivo/laminas/{nombre}'})
        if accion == 'voces':
            # audios de la autora recitando (Archivo/voces/), para la acción
            # «voz de lector»
            carpeta = os.path.join(HERE, 'Archivo', 'voces')
            nombres = sorted(f for f in os.listdir(carpeta) if VOZ_OK.match(f)) if os.path.isdir(carpeta) else []
            return self._json(200, {'ok': True, 'voces': nombres})
        if accion == 'voz':
            nombre = datos.get('nombre') or ''
            if not VOZ_OK.match(nombre) or not isinstance(datos.get('datos'), str):
                return self._json(400, {'ok': False, 'error': 'nombre o datos inválidos'})
            try:
                crudo = base64.b64decode(datos['datos'], validate=True)
            except (ValueError, binascii.Error):
                return self._json(400, {'ok': False, 'error': 'datos inválidos'})
            if len(crudo) > 25 * 1024 * 1024:
                return self._json(400, {'ok': False, 'error': 'pasa de 25 MB'})
            carpeta = os.path.join(HERE, 'Archivo', 'voces')
            os.makedirs(carpeta, exist_ok=True)
            with open(os.path.join(carpeta, nombre), 'wb') as f:
                f.write(crudo)
            return self._json(200, {'ok': True, 'log': f'✓ Archivo/voces/{nombre}'})
        if accion == 'subir':
            ok, log = subir()
            return self._json(200, {'ok': ok, 'log': log})
        return self._json(404, {'ok': False, 'error': 'acción desconocida'})


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), partial(Manejador, directory=HERE))
    print(f'Sitio en http://localhost:{puerto}/  ·  taller: http://localhost:{puerto}/uploader-v1.html')
    print('El botón ⚡ publicar corre los scripts desde acá. Ctrl+C para cortar.')
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('\nlisto.')


if __name__ == '__main__':
    main()
