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

# guardar "mensaje" ruta...: commitea esas rutas en main del repo privado.
# Si mientras tanto entró otro commit, se lo trae y reintenta. Con
# ESTRATEGIA=theirs (solo para pasos que escriben archivos calculados), los
# archivos que este paso cambió se toman enteros de la versión recién
# calculada sobre lo último de main; el resto de main queda como está. No se
# mezclan línea a línea: dos JSON calculados mezclados así salen válidos pero
# rotos (una propuesta sin «destino» tumbó Superficie el 14/10/2026).
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
  local mio cambiados=() f
  mio=$(git rev-parse HEAD)
  mapfile -t cambiados < <(git diff --name-only --no-renames "$mio~1" "$mio")
  for i in 1 2 3 4; do
    if git push -q origin HEAD:main >> "$REGISTRO" 2>&1; then
      echo "✓ guardado en el repo privado"
      return 0
    fi
    sleep $((i * 3))
    if [ "${ESTRATEGIA:-}" = theirs ]; then
      git fetch -q origin main >> "$REGISTRO" 2>&1 || return 1
      git reset -q --hard origin/main >> "$REGISTRO" 2>&1
      for f in "${cambiados[@]}"; do
        if git cat-file -e "$mio:$f" 2>/dev/null; then
          git checkout -q "$mio" -- "$f" >> "$REGISTRO" 2>&1
        else
          git rm -q --ignore-unmatch -- "$f" >> "$REGISTRO" 2>&1
        fi
      done
      git diff --cached --quiet && { echo "· sin cambios que guardar"; return 0; }
      git commit -q -m "$msg" >> "$REGISTRO" 2>&1
    else
      git pull -q --rebase origin main >> "$REGISTRO" 2>&1 || { git rebase --abort || true; return 1; }
    fi
  done
  echo "✗ no se pudo guardar en el repo privado"
  return 1
}

# al_dia: trae lo último de main (para pasos largos que arrancaron antes).
al_dia() {
  git -C "$REPO_DIR" pull -q --rebase origin main >> "$REGISTRO" 2>&1
}

# marcar NOMBRE SHA: deja la rama estado/NOMBRE del repo privado en SHA, el
# commit desde el que se calculó. vigilar.yml compara main contra esa rama
# para saber si hay algo nuevo (ver vigilar.sh).
marcar() {
  git -C "$REPO_DIR" push -q -f origin "$2:refs/heads/estado/$1" >> "$REGISTRO" 2>&1
}
