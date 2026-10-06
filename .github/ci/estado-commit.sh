#!/usr/bin/env bash
# estado-commit.sh ESTADO "descripción": pone el estado «comprobar» en el
# commit del repo privado que se está comprobando.
. "$(dirname "$0")/comun.sh"
SHA=$(entrada sha)
case "$SHA" in ''|*[!0-9a-f]*) echo "✗ sha inválido"; exit 1;; esac
GH_TOKEN="$P314B_TOKEN" gh api -X POST "repos/$PRIVADO/statuses/$SHA" \
  -f state="$1" -f context=comprobar -f description="$2" \
  -f target_url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" > /dev/null
echo "estado del commit: $1"
