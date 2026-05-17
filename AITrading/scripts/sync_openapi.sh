#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="${1:-"$ROOT/../AITradingFrontend"}"

if [[ ! -f "$ROOT/openapi.yaml" ]]; then
  echo "Missing backend OpenAPI: $ROOT/openapi.yaml" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND" ]]; then
  echo "Missing frontend directory: $FRONTEND" >&2
  exit 1
fi

cp "$ROOT/openapi.yaml" "$FRONTEND/openapi.yaml"
echo "Synced $ROOT/openapi.yaml -> $FRONTEND/openapi.yaml"

