#!/usr/bin/env sh
set -eu

SETTINGS_FILE="/etc/searxng/settings.yml"

if [ ! -s "$SETTINGS_FILE" ]; then
  echo "FATAL: missing or empty $SETTINGS_FILE" >&2
  exit 64
fi

if ! grep -Eq '^[[:space:]]*-[[:space:]]*json[[:space:]]*$' "$SETTINGS_FILE"; then
  echo "FATAL: $SETTINGS_FILE missing required 'search.formats: - json' entry" >&2
  exit 65
fi

exec /usr/local/searxng/entrypoint-base.sh "$@"
