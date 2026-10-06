#!/usr/bin/env bash
# Sube web/ (y el Worker) a Cloudflare con wrangler, desde el repo privado.
. "$(dirname "$0")/comun.sh"
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  echo "::warning title=Sin deploy::Falta el secreto CLOUDFLARE_API_TOKEN: web/ quedó en main pero no se subió a Cloudflare."
  exit 0
fi
cd "$REPO_DIR"
callado "subir a Cloudflare (wrangler deploy)" npx --yes wrangler@4 deploy
