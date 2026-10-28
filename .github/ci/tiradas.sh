#!/usr/bin/env bash
# Tiradas: semillas nuevas para las pruebas al azar (medir.py --rondas) y
# estados de los conceptos. Escribe solo sitio/matriz/.
. "$(dirname "$0")/comun.sh"

RONDAS=$(entrada rondas)
[[ "$RONDAS" =~ ^[0-9]+$ ]] && (( RONDAS >= 1 && RONDAS <= 20 )) || RONDAS=4
cd "$REPO_DIR/sitio"
callado "tiradas ($RONDAS rondas)" python matriz/medir.py --rondas "$RONDAS"
callado "estados de los conceptos" python matriz/estados.py
ESTRATEGIA=theirs guardar "Matriz: tiradas acumuladas" sitio/matriz
