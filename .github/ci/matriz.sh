#!/usr/bin/env bash
# Matriz relacional: índice de pasajes, pesos, propuestas, recorridos y capa
# autónoma, medidas y estados de los conceptos (lo que hacía matriz.yml). Escribe solo sitio/matriz/.
. "$(dirname "$0")/comun.sh"

ORIGEN=$(git -C "$REPO_DIR" rev-parse HEAD)
cd "$REPO_DIR/sitio"
callado "índice de pasajes" python matriz/indexar_pasajes.py
callado "pesos de los instrumentos" python matriz/recalibrar.py
callado "propuestas (vectores)" python matriz/proponer_cruces.py
callado "recorridos" python matriz/calcular_recorridos.py
callado "capa autónoma" python matriz/autonoma.py
callado "relaciones de la matriz" python matriz/relaciones.py
callado "medidas de los conceptos" python matriz/medir.py
callado "estados de los conceptos" python matriz/estados.py
ESTRATEGIA=theirs guardar "Matriz: propuestas y recorridos al día" sitio/matriz
marcar matriz "$ORIGEN"
