# Lo comparten todos los pasos (se carga con «. _ci/.github/ci/comun.sh»).
#
# Este repo es público: los registros de Actions los puede leer cualquiera.
# Por eso nada de lo que corre sobre el repo privado (p4p13b/p314b) escribe
# en el registro: todo va a $REGISTRO, y en pantalla solo queda «✓ paso» o
# «✗ paso». Si algo falla, el paso «Guardar el registro» sube el detalle a
# registros/ del repo privado (ver registro.sh).
set -euo pipefail

PRIVADO="p4p13b/p314b"
REPO_DIR="$GITHUB_WORKSPACE/p314b"
REGISTRO="$RUNNER_TEMP/registro.log"
CI="$GITHUB_WORKSPACE/_ci/.github/ci"
touch "$REGISTRO"

# Rama del repo privado sobre la que se trabaja: main (el sitio público) o
# pruebas (pruebas.p314b.space). Viene del disparo (input «rama»); si no,
# main. En pruebas, publicar.py marca el sitio como de pruebas.
RAMA=$(jq -r '.inputs.rama // empty' "${GITHUB_EVENT_PATH:-/dev/null}" 2>/dev/null || true)
RAMA=${RAMA:-main}
case "$RAMA" in main|pruebas) ;; *) echo "✗ rama inválida"; exit 1;; esac
[ "$RAMA" = pruebas ] && export P314B_ENTORNO=pruebas

# callado "qué es" comando...: corre el comando con la salida al registro.
callado() {
  local que="$1"; shift
  printf '\n== %s\n' "$que" >> "$REGISTRO"
  if "$@" >> "$REGISTRO" 2>&1; then
    echo "✓ $que"
  else
    echo "✗ $que (el detalle queda en registros/ del repo privado)"
    return 1
  fi
}

# Dato de un disparo manual (workflow_dispatch). Se lee del evento, no de
# ${{ inputs }}: lo que pasa por «env:» se imprime en el registro público.
entrada() {
  jq -r --arg k "$1" '.inputs[$k] // ""' "$GITHUB_EVENT_PATH"
}

# guardar "mensaje" ruta...: commitea esas rutas en $RAMA del repo privado.
# Si mientras tanto entró otro commit, se lo trae y reintenta. Con
# ESTRATEGIA=theirs, si chocan con otra versión de los mismos archivos gana
# la recién calculada (solo para pasos que escriben archivos calculados).
guardar() {
  local msg="$1"; shift
  cd "$REPO_DIR"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A -- "$@" >> "$REGISTRO" 2>&1
  if git diff --cached --quiet; then
    echo "· sin cambios que guardar"
    return 0
  fi
  git commit -q -m "$msg" >> "$REGISTRO" 2>&1
  local x=()
  [ "${ESTRATEGIA:-}" = theirs ] && x=(-X theirs)
  for i in 1 2 3 4; do
    if git push -q origin "HEAD:$RAMA" >> "$REGISTRO" 2>&1; then
      echo "✓ guardado en el repo privado"
      return 0
    fi
    sleep $((i * 3))
    git pull -q --rebase "${x[@]}" origin "$RAMA" >> "$REGISTRO" 2>&1 || { git rebase --abort || true; return 1; }
  done
  echo "✗ no se pudo guardar en el repo privado"
  return 1
}

# al_dia: trae lo último de $RAMA (para pasos largos que arrancaron antes).
al_dia() {
  git -C "$REPO_DIR" pull -q --rebase origin "$RAMA" >> "$REGISTRO" 2>&1
}

# marcar NOMBRE SHA: deja la rama estado/NOMBRE del repo privado en SHA, el
# commit desde el que se calculó. vigilar.yml compara main contra esa rama
# para saber si hay algo nuevo (ver vigilar.sh).
marcar() {
  local nombre="$1"
  [ "$RAMA" = main ] || nombre="$1-$RAMA"
  git -C "$REPO_DIR" push -q -f origin "$2:refs/heads/estado/$nombre" >> "$REGISTRO" 2>&1
}
