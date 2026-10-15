#!/usr/bin/env bash
# Matriz de lectores: baja los pasos que el celular manda a /api/camino y
# escribe sitio/matriz/lectores-matriz.json (lo que hacía lectores.yml). Con
# la opción «reiniciar» vacía antes lo capturado (DELETE /api/caminos).
. "$(dirname "$0")/comun.sh"

if [ "$(entrada reiniciar)" = true ]; then
  callado "reiniciar lo capturado en el celular" \
    curl -fsS -X DELETE -H "Authorization: Bearer $P314B_TOKEN" https://www.p314b.space/api/caminos
fi

cd "$REPO_DIR/sitio"
callado "lectores del celular" python matriz/lectores.py --bajar
ESTRATEGIA=theirs guardar "Lectores: matriz de lectores al día" sitio/matriz/lectores-matriz.json
