#!/usr/bin/env bash
set -euo pipefail

# Bug Fix Kit local one-click dev install.
#
# Refreshes the locally installed Codex plugin from the current source checkout
# so changes to skills / CLI / mechanics are picked up on the next Codex session.
#
# Steps:
#   1. Read plugin name + version from .codex-plugin/plugin.json.
#   2. Clear the stale Codex plugin cache for this version.
#   3. Sync the editable package (uv preferred, pip fallback).
#   4. Copy/register the plugin into ~/plugins + personal marketplace.
#   5. Run `bfk doctor` to confirm the plugin shell is healthy.
#
# Extra args are forwarded to `bfk install`, e.g.:
#   scripts/dev-refresh-install.sh --home /tmp/fake-home

cd "$(dirname "${BASH_SOURCE[0]}")/.."

DEFAULT_CACHE_ROOT="${HOME}/.codex/plugins/cache/personal"
CACHE_ROOT="${CODEX_PERSONAL_PLUGIN_CACHE_ROOT:-$DEFAULT_CACHE_ROOT}"

read -r PLUGIN_NAME VERSION < <(
  python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
name = str(manifest.get("name", "")).strip()
version = str(manifest.get("version", "")).strip()
if not name:
    raise SystemExit("missing .codex-plugin/plugin.json name")
if not version:
    raise SystemExit("missing .codex-plugin/plugin.json version")
print(name, version)
PY
)

if [[ -z "${PLUGIN_NAME}" || -z "${VERSION}" ]]; then
  echo "error: could not read plugin name/version from plugin.json" >&2
  exit 2
fi

CACHE_DIR="${CACHE_ROOT%/}/${PLUGIN_NAME}/${VERSION}"

echo "Bug Fix Kit dev refresh install"
echo "repo:        $(pwd)"
echo "plugin:      ${PLUGIN_NAME} ${VERSION}"
echo "cache root:  ${CACHE_ROOT}"

if [[ -e "${CACHE_DIR}" || -L "${CACHE_DIR}" ]]; then
  echo "clearing Codex plugin cache: ${CACHE_DIR}"
  rm -rf "${CACHE_DIR}"
else
  echo "Codex plugin cache already absent: ${CACHE_DIR}"
fi

if command -v uv >/dev/null 2>&1; then
  echo "syncing editable package with uv"
  uv sync
  RUN=(uv run)
else
  echo "uv not found; installing editable package with pip"
  python3 -m pip install -e . >/dev/null
  RUN=()
fi

echo "installing local checkout into personal marketplace"
"${RUN[@]}" bfk install --yes "$@"

echo "checking local plugin shell"
"${RUN[@]}" bfk doctor

echo
echo "done."
echo "next: run 'codex plugin add ${PLUGIN_NAME}@personal', then enable Bug Fix Kit in Codex /plugins"
echo "if skills do not appear immediately, open a new Codex thread."
