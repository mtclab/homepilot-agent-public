#!/bin/bash
# Initialize Zabbix monitoring stack
# Run this once after first `docker compose ... up -d`
#
# Loads .env.monitoring and calls init_zabbix.py with the right arguments.
#
# Usage: bash scripts/init-zabbix.sh [--pve-url URL] [--pve-token-id ID]
#                                     [--pve-token-secret SECRET]
#                                     [--agent-hostname NAME] [--agent-ip IP]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment
if [ -f "${COMPOSE_DIR}/.env.monitoring" ]; then
    set -a
    source "${COMPOSE_DIR}/.env.monitoring"
    set +a
fi

# Detect host IP if not set
AGENT_IP="${AGENT_IP:-}"
if [ -z "${AGENT_IP}" ]; then
    AGENT_IP=$(ip route show default 2>/dev/null | awk '{print $3}' | head -1)
    # If default route IP is a gateway (e.g. Docker), use the host's own IP
    if [ -z "${AGENT_IP}" ] || [ "${AGENT_IP}" = "127.0.0.1" ]; then
        AGENT_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
fi

AGENT_HOSTNAME="${AGENT_HOSTNAME:-$(hostname -f)}"
ZABBIX_URL="${ZABBIX_URL:-http://localhost:8084}"
ZABBIX_USER="${ZABBIX_USER:-Admin}"
ZABBIX_PASSWORD="${ZABBIX_PASSWORD:-zabbix}"

echo "=== Zabbix Monitoring Stack Initialization ==="
echo "Zabbix URL: ${ZABBIX_URL}"
echo "Agent hostname: ${AGENT_HOSTNAME}"
echo "Agent IP: ${AGENT_IP}"

exec python3 "${SCRIPT_DIR}/init_zabbix.py" \
    --url "${ZABBIX_URL}" \
    --user "${ZABBIX_USER}" \
    --password "${ZABBIX_PASSWORD}" \
    ${ZBX_ADMIN_PASSWORD:+--new-password "${ZBX_ADMIN_PASSWORD}"} \
    ${PVE_URL:+--pve-url "${PVE_URL}"} \
    ${PVE_TOKEN_ID:+--pve-token-id "${PVE_TOKEN_ID}"} \
    ${PVE_TOKEN_SECRET:+--pve-token-secret "${PVE_TOKEN_SECRET}"} \
    --agent-hostname "${AGENT_HOSTNAME}" \
    --agent-ip "${AGENT_IP}"