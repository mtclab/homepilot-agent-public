#!/usr/bin/env bash
set -euo pipefail

# Imports all n8n workflow JSONs from n8n/workflows/ into a running n8n instance.
# Run after docker compose up on a fresh deploy.
#
# Requires:
#   - n8n running and accessible at N8N_HOST:5678
#   - N8N_API_KEY set in .env (create in n8n Settings → API)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKFLOWS_DIR="${REPO_ROOT}/n8n/workflows"

# Load .env if present
if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.env"
    set +o allexport
fi

N8N_HOST="${N8N_HOST:-localhost}"
N8N_PORT="${N8N_PORT:-5678}"
N8N_API_KEY="${N8N_API_KEY:-}"
N8N_BASE_URL="http://${N8N_HOST}:${N8N_PORT}"

if [[ -z "${N8N_API_KEY}" ]]; then
    echo "ERROR: N8N_API_KEY not set." >&2
    echo "  Create an API key in n8n Settings → API, then add it to .env." >&2
    exit 1
fi

echo "Connecting to n8n at ${N8N_BASE_URL}..."

# Wait for n8n to be ready
max_wait=60
elapsed=0
until curl -sf "${N8N_BASE_URL}/healthz" >/dev/null 2>&1; do
    if [[ ${elapsed} -ge ${max_wait} ]]; then
        echo "ERROR: n8n not reachable after ${max_wait}s" >&2
        exit 1
    fi
    echo "Waiting for n8n..."
    sleep 3
    elapsed=$((elapsed + 3))
done

echo "n8n is ready."

import_workflow() {
    local file="$1"
    local name
    name=$(basename "${file}" .json)

    echo -n "  Importing ${name}... "

    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        -H "Content-Type: application/json" \
        --data "@${file}" \
        "${N8N_BASE_URL}/api/v1/workflows")

    if [[ "${http_status}" == "200" || "${http_status}" == "201" ]]; then
        echo "OK (${http_status})"
    else
        echo "FAILED (HTTP ${http_status})" >&2
        return 1
    fi
}

failed=0
for wf_file in "${WORKFLOWS_DIR}"/*.json; do
    import_workflow "${wf_file}" || failed=$((failed + 1))
done

if [[ ${failed} -gt 0 ]]; then
    echo ""
    echo "WARNING: ${failed} workflow(s) failed to import." >&2
    echo "  Duplicate names fail — if workflows already exist, delete them in n8n UI first." >&2
    exit 1
fi

echo ""
echo "All workflows imported."
echo ""
echo "Next steps:"
echo "  1. Open n8n at ${N8N_BASE_URL}"
echo "  2. Set up credentials (Telegram, LLM API, HomePilot MCP, Matrix)"
echo "     See README.md → Credentials section for required credential names."
echo "  3. Activate each workflow."
