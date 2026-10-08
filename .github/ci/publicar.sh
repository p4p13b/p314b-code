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

if [ -n "$ELIMINAR" ]; then MSG="Sacar $ELIMINAR del sitio ($MODO)"; else MSG="Publicar ${OBRA:-sitio} (web/ al día)"; fi
armar_y_guardar() {
  cd "$REPO_DIR/sitio"
  callado "armar el sitio (pasos.py)" python pasos.py --obra "$OBRA" || return 1
  # Si web/ salió rota (un JSON inválido, un token de plantilla sin
  # reemplazar, una obra sin su página), no se guarda ni se sube.
  callado "comprobar web/" python ../tests/comprobar_web.py || return 1
  guardar "$MSG" sitio web $(resumen)
}
# registros/ultima-publicacion.md: lo escribe pasos.py (qué obras se
# regeneraron, cuáles no y por qué, diagonales, errores). Se guarda con
# web/ para que un aviso que no hace fallar el paso se pueda leer en el
# repo privado; acá no se imprime nada.
resumen() {
  [ -f "$REPO_DIR/registros/ultima-publicacion.md" ] && echo registros/ultima-publicacion.md || true
}
# Si mientras se armaba entró otra publicación o la matriz, los archivos
# calculados chocan: se descarta lo armado, se trae main y se vuelve a
# armar sobre lo último (una vez). Con «eliminar» no: lo que hizo
# eliminar_obra.py se perdería al traer main.
if ! armar_y_guardar; then
  [ -z "$ELIMINAR" ] || exit 1
  echo "· chocó con otro cambio en main: se vuelve a armar sobre lo último"
  git -C "$REPO_DIR" rebase --abort >> "$REGISTRO" 2>&1 || true
  git -C "$REPO_DIR" fetch -q origin main >> "$REGISTRO" 2>&1
  git -C "$REPO_DIR" reset -q --hard origin/main >> "$REGISTRO" 2>&1
  git -C "$REPO_DIR" clean -qfd -- sitio web >> "$REGISTRO" 2>&1
  ORIGEN=$(git -C "$REPO_DIR" rev-parse HEAD)
  if ! armar_y_guardar; then
    # Sin web/ nueva igual queda el resumen de por qué: se lo aparta, se
    # vuelve a main tal cual (nada de lo armado se guarda) y se guarda solo
    # ese archivo.
    if [ -n "$(resumen)" ]; then
      cp "$REPO_DIR/registros/ultima-publicacion.md" "$RUNNER_TEMP/resumen.md"
      git -C "$REPO_DIR" rebase --abort >> "$REGISTRO" 2>&1 || true
      git -C "$REPO_DIR" fetch -q origin main >> "$REGISTRO" 2>&1 || true
      git -C "$REPO_DIR" reset -q --hard origin/main >> "$REGISTRO" 2>&1 || true
      mkdir -p "$REPO_DIR/registros"
      cp "$RUNNER_TEMP/resumen.md" "$REPO_DIR/registros/ultima-publicacion.md"
      guardar "Publicación fallida: resumen [skip ci]" registros/ultima-publicacion.md || true
    fi
    exit 1
  fi
fi
marcar publicar "$ORIGEN"
