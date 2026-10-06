#!/usr/bin/env bash
# Manifest del Archivo, términos para resaltar y terceros pendientes (el paso
# 3 de «Actualizar todo»).
. "$(dirname "$0")/comun.sh"
cd "$REPO_DIR/sitio"
callado "manifest del Archivo" python actualizar_archivo.py
callado "términos para resaltar" python terminos.py
callado "terceros pendientes" python tercero_demanda.py
guardar "Actualizar todo: archivo, términos y terceros al día" \
  sitio/Archivo/manifest.json sitio/terminos.json sitio/acciones.json sitio/obras
