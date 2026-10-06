#!/usr/bin/env bash
# Decide qué hay que correr comparando main del repo privado con las ramas
# estado/<nombre> (las deja cada workflow al terminar bien: el commit desde
# el que calculó). Solo cuentan los commits de personas, no los del bot.
#
#   publicar    sitio/, datos-lee/cowork/CRONOLOGIA.md, datos-lee/txt/,
#               worker/, wrangler.jsonc, web/. No cuentan los commits con
#               [skip ci]: son guardados del taller que ya lanzan la
#               publicación ellos mismos.
#   superficie  lemas.json, lemas_auto.py, obras/*.json, el manifest del
#               Archivo, los scripts del anexo, datos-lee/txt/.
#   matriz      sitio/matriz/decisiones.json.
#
# Si ese workflow ya está corriendo o en cola, no lo lanza de nuevo: lo
# nuevo lo agarra la próxima vuelta. En el registro (público) solo quedan
# cantidades, nunca nombres de archivos ni mensajes de commit.
. "$(dirname "$0")/comun.sh"

if [ -z "${P314B_TOKEN:-}" ]; then
  echo "::warning title=Sin token::Falta el secreto P314B_TOKEN: no se puede mirar el repo privado."
  exit 0
fi

cd "$RUNNER_TEMP"
# Sin contenidos de archivos (--filter=blob:none): alcanza con la historia.
git clone -q --filter=blob:none --no-checkout \
  "https://x-access-token:${P314B_TOKEN}@github.com/$PRIVADO.git" privado >> "$REGISTRO" 2>&1
cd privado

nuevos() {   # nuevos NOMBRE SALTAR_SKIP_CI ruta... → cantidad de commits
  local base="origin/estado/$1" saltar="$2"; shift 2
  if ! git rev-parse -q --verify "$base" > /dev/null; then echo 1; return; fi
  git log "$base..origin/main" --format='%an%x09%s' -- "$@" |
    awk -F'\t' -v s="$saltar" '$1 != "github-actions[bot]" && !(s == 1 && index($2, "[skip ci]"))' |
    wc -l
}

ocupado() {  # ocupado WORKFLOW → 1 si hay una corrida en curso o en cola
  local n
  n=$(gh run list --workflow "$1" --limit 20 --json status \
        --jq '[.[] | select(.status != "completed")] | length')
  [ "$n" -gt 0 ]
}

lanzar() {   # lanzar NOMBRE CANTIDAD
  if [ "$2" -eq 0 ]; then echo "· $1: nada nuevo"; return; fi
  if ocupado "$1.yml"; then echo "· $1: $2 commit(s) nuevos, ya hay una corrida en curso"; return; fi
  gh workflow run "$1.yml" --ref main > /dev/null
  echo "✓ $1: $2 commit(s) nuevos, lanzado"
}

lanzar publicar   "$(nuevos publicar 1 sitio datos-lee/cowork/CRONOLOGIA.md datos-lee/txt worker wrangler.jsonc web)"
lanzar superficie "$(nuevos superficie 0 sitio/lemas.json sitio/lemas_auto.py 'sitio/obras/*.json' sitio/Archivo/manifest.json sitio/matriz/anexo/scripts datos-lee/txt)"
lanzar matriz     "$(nuevos matriz 0 sitio/matriz/decisiones.json)"

# PR abiertas del repo privado que tocan el sitio y no tienen el estado
# «comprobar» en su último commit.
RUTAS_PR=(sitio datos-lee/cowork/CRONOLOGIA.md datos-lee/txt tests worker)
pendientes=0
while read -r sha; do
  [ -n "$sha" ] || continue
  git cat-file -e "$sha^{commit}" 2> /dev/null || continue
  [ -n "$(git diff --name-only "origin/main...$sha" -- "${RUTAS_PR[@]}" 2>> "$REGISTRO" | head -1)" ] || continue
  hay=$(GH_TOKEN="$P314B_TOKEN" gh api "repos/$PRIVADO/commits/$sha/statuses" \
          --jq '[.[] | select(.context == "comprobar")] | length')
  [ "$hay" -eq 0 ] || continue
  gh workflow run comprobar.yml --ref main -f sha="$sha" > /dev/null
  pendientes=$((pendientes + 1))
done < <(GH_TOKEN="$P314B_TOKEN" gh pr list -R "$PRIVADO" --state open --limit 50 --json headRefOid --jq '.[].headRefOid')
echo "· PR: $pendientes para comprobar"

# Un repo público sin commits apaga sus workflows con reloj a los 60 días.
# Volver a activarlos reinicia la cuenta.
for wf in vigilar matriz superficie; do
  gh api -X PUT "repos/$GITHUB_REPOSITORY/actions/workflows/$wf.yml/enable" > /dev/null 2>&1 || true
done
