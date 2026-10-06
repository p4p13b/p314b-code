#!/usr/bin/env bash
# Si algo falló, sube el registro completo a registros/ del repo privado
# (ahí sí se puede leer el detalle sin que quede público).
. "$(dirname "$0")/comun.sh"
[ -s "$REGISTRO" ] || exit 0
NOMBRE="registros/$(date -u +%Y-%m-%d-%H%M)-$1-$GITHUB_RUN_ID.log"
python3 - "$REGISTRO" "$NOMBRE" > "$RUNNER_TEMP/registro.json" <<'PY'
import base64, json, sys
datos = open(sys.argv[1], 'rb').read()[-900_000:]
print(json.dumps({
    'message': 'registro: ' + sys.argv[2].split('/')[-1] + ' [skip ci]',
    'content': base64.b64encode(datos).decode(),
    'branch': 'main',
}))
PY
GH_TOKEN="$P314B_TOKEN" gh api -X PUT "repos/$PRIVADO/contents/$NOMBRE" --input "$RUNNER_TEMP/registro.json" > /dev/null
echo "El detalle quedó en el repo privado: $NOMBRE"
