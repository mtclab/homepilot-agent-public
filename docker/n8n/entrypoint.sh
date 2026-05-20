#!/bin/sh
set -e

# n8n entrypoint wrapper — reads Docker secrets from files and exports as env vars.
# Backward compatible: if _FILE var points to a file, read from it; otherwise use env var.

# N8N_ENCRYPTION_KEY: prefer file-based secret, fall back to env var
if [ -n "${N8N_ENCRYPTION_KEY_FILE:-}" ] && [ -f "${N8N_ENCRYPTION_KEY_FILE}" ]; then
    export N8N_ENCRYPTION_KEY="$(cat "${N8N_ENCRYPTION_KEY_FILE}" | tr -d '[:space:]')"
elif [ -z "${N8N_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: N8N_ENCRYPTION_KEY not set via env var or secret file" >&2
    exit 1
fi

# HP_MCP_TOKEN: prefer file-based secret, fall back to env var
if [ -n "${HP_MCP_TOKEN_FILE:-}" ] && [ -f "${HP_MCP_TOKEN_FILE}" ]; then
    export HP_MCP_TOKEN="$(cat "${HP_MCP_TOKEN_FILE}" | tr -d '[:space:]')"
fi

# HP_MCP_TOKEN_RW: prefer file-based secret, fall back to env var
if [ -n "${HP_MCP_TOKEN_RW_FILE:-}" ] && [ -f "${HP_MCP_TOKEN_RW_FILE}" ]; then
    export HP_MCP_TOKEN_RW="$(cat "${HP_MCP_TOKEN_RW_FILE}" | tr -d '[:space:]')"
fi

exec tini -- "$@"