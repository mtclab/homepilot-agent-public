#!/usr/bin/env sh
set -e

if [ -n "${SEARXNG_SECRET_KEY_FILE:-}" ] && [ -f "${SEARXNG_SECRET_KEY_FILE}" ]; then
    export SEARXNG_SECRET_KEY="$(cat "${SEARXNG_SECRET_KEY_FILE}" | tr -d '[:space:]')"
fi

exec /usr/local/searxng/entrypoint.sh "$@"