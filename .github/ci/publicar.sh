#!/usr/bin/env bash
# Arma web/ en el repo privado y la guarda en main (lo que hacía publicar.yml).
# Con «eliminar», antes saca esas obras del sitio (eliminar_obra.py).
. "$(dirname "$0")/comun.sh"

OBRA=$(entrada obra)
ELIMINAR=$(entrada eliminar)
MODO=$(entrada modo)
case "$OBRA" in *[!a-z0-9-]*) echo "✗ slug inválido"; exit 1;; esac

ORIGEN=$(git -C "$REPO_DIR" rev-parse HEAD)
cd "$REPO_DIR/sitio"
callado "dependencias" pip install --quiet pypdf

if [ -n "$ELIMINAR" ]; then
  # Varias obras en una corrida: sigue aunque alguna no se pueda (p. ej.
  # otra obra publicada tiene una diagonal hacia ella).
  hechas=0; total=0
  for slug in $ELIMINAR; do
    total=$((total + 1))
    case "$slug" in *[!a-z0-9-]*) echo "slug inválido: $slug" >> "$REGISTRO"; continue;; esac
    if [ "$MODO" = eliminar ]; then extra=(); else extra=(--ocultar); fi
    if python eliminar_obra.py "$slug" "${extra[@]}" >> "$REGISTRO" 2>&1; then
      hechas=$((hechas + 1))
    else
      echo "✗ no se pudo: $slug" >> "$REGISTRO"
    fi
  done
  echo "$hechas de $total obra(s) sacadas"
  [ "$hechas" -gt 0 ] || { echo "✗ no se pudo sacar ninguna"; exit 1; }
fi

callado "armar el sitio (pasos.py)" python pasos.py --obra "$OBRA"
# Si web/ salió rota (un JSON inválido, un token de plantilla sin
# reemplazar, una obra sin su página), no se guarda ni se sube.
callado "comprobar web/" python ../tests/comprobar_web.py

if [ -n "$ELIMINAR" ]; then MSG="Sacar $ELIMINAR del sitio ($MODO)"; else MSG="Publicar ${OBRA:-sitio} (web/ al día)"; fi
guardar "$MSG" sitio web
marcar publicar "$ORIGEN"
