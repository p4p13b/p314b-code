#!/usr/bin/env bash
# Lemas del diccionario, índice de pasajes, anexo, superficie relacional y
# familias de palabras (lo que hacía superficie.yml). Con «publicar» como
# argumento, si cambió algo de lo que se publica lanza publicar.yml.
. "$(dirname "$0")/comun.sh"

ORIGEN=$(git -C "$REPO_DIR" rev-parse HEAD)
cd "$REPO_DIR/sitio"
callado "lemas del diccionario" python lemas_auto.py
callado "índice de pasajes" python matriz/indexar_pasajes.py
callado "anexo y superficie relacional" sh matriz/anexo/scripts/correr.sh
callado "familias de palabras" python ../pulenta/scripts/familias.py
# la página «tercero» (Aire | tercero | Embriaguez): usa el anexo recién armado
( cd matriz/anexo/scripts && callado "terceros de la página «tercero»" python tercero.py )
cd "$REPO_DIR"
callado "las tres lematizaciones dan lo mismo" python tests/test_lematizacion.py

PUBLICADOS=(sitio/lemas-auto.json sitio/gemelas.json sitio/tercero.json pulenta/datos/familias.json)
cambio_publicado=0
[ -n "$(git status --porcelain -- "${PUBLICADOS[@]}")" ] && cambio_publicado=1

ESTRATEGIA=theirs guardar "Superficie: lemas del diccionario y anexo al día" \
  sitio/lemas-auto.json sitio/gemelas.json sitio/tercero.json sitio/matriz/superficie sitio/matriz/anexo/datos pulenta/datos
marcar superficie "$ORIGEN"

if [ "${1:-}" = publicar ] && [ "$cambio_publicado" = 1 ]; then
  gh workflow run publicar.yml --ref main > /dev/null && echo "✓ cambió algo publicado: se lanzó «Publicar sitio»"
fi
