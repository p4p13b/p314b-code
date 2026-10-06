#!/usr/bin/env bash
# Arma web/ como al publicar (sin guardar nada) y la prueba en Chromium.
. "$(dirname "$0")/comun.sh"
cd "$REPO_DIR/sitio"
callado "dependencias" pip install --quiet pypdf playwright
callado "Chromium" python -m playwright install --with-deps chromium
callado "armar web/ (pasos.py)" python pasos.py
cd "$REPO_DIR"
callado "comprobar web/ en el navegador" python tests/comprobar_web.py --navegador
