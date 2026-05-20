#!/usr/bin/env bash
# Zabbix → Matrix webhook alert script.
# Called by Zabbix script media type. Sends alert notifications to a Matrix room.
#
# Environment variables:
#   MATRIX_SERVER  — Matrix homeserver URL
#   MATRIX_ROOM_ID — Target room ID
#   MATRIX_TOKEN   — Bot access token
#   ZABBIX_ALERT_SUBJECT / ALERT_SUBJECT — Trigger name (positional arg $1)
#   ZABBIX_ALERT_MESSAGE / ALERT_MESSAGE — Full alert message (positional arg $2)
#   ZABBIX_URL — Link to event in Zabbix UI (positional arg $3)

set -euo pipefail

SUBJECT="${ZABBIX_ALERT_SUBJECT:-${ALERT_SUBJECT:-${1:-Zabbix Alert}}}"
MESSAGE="${ZABBIX_ALERT_MESSAGE:-${ALERT_MESSAGE:-${2:-}}}"
ZABBIX_URL="${ZABBIX_URL:-${3:-}}"
SERVER="${MATRIX_SERVER:-}"
ROOM_ID="${MATRIX_ROOM_ID:-}"
TOKEN="${MATRIX_TOKEN:-}"

if [[ -z "$SERVER" || -z "$ROOM_ID" || -z "$TOKEN" ]]; then
    echo "ERROR: Missing environment variables." >&2
    echo "MATRIX_SERVER=${SERVER:-missing}, MATRIX_ROOM_ID=${ROOM_ID:+set}${ROOM_ID:-missing}, MATRIX_TOKEN=${TOKEN:+set}${TOKEN:-missing}" >&2
    exit 1
fi

SERVER="${SERVER%/}"

SEVERITY="UNKNOWN"
while IFS= read -r line; do
    case "$line" in
        *Disaster*|*disaster*) SEVERITY="DISASTER" ;;
        *High*|*high*) SEVERITY="HIGH" ;;
        *Average*|*average*) SEVERITY="AVERAGE" ;;
        *Warning*|*warning*) SEVERITY="WARNING" ;;
        *Information*|*information*) SEVERITY="INFORMATION" ;;
    esac
    if [[ "$SEVERITY" != "UNKNOWN" ]]; then
        break
    fi
done <<< "$MESSAGE"

case "$SEVERITY" in
    DISASTER)      ICON="🔴" ;;
    HIGH)          ICON="🟠" ;;
    AVERAGE|WARNING) ICON="🟡" ;;
    INFORMATION)   ICON="🔵" ;;
    *)             ICON="⚪" ;;
esac

BODY="${ICON} **[${SEVERITY}] ${SUBJECT}**\n\n${MESSAGE}"
if [[ -n "$ZABBIX_URL" ]]; then
    BODY="${BODY}\n\n[View in Zabbix](${ZABBIX_URL})"
fi

TXN_ID="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"

URL="${SERVER}/_matrix/client/v3/rooms/${ROOM_ID}/send/m.room.message/${TXN_ID}"

# Build JSON payload safely: escape special chars for JSON string
ESCAPED_BODY=$(printf '%s' "$BODY" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g' | tr '\n' ' ')
PAYLOAD=$(printf '{"msgtype":"m.text","body":"%s"}' "$ESCAPED_BODY")

HTTP_CODE=$(wget -qO- --server-response --header="Content-Type: application/json" \
    --header="Authorization: Bearer ${TOKEN}" \
    --method=PUT \
    --body-data="${PAYLOAD}" \
    "${URL}" 2>&1 | head -1)

if [[ "${HTTP_CODE}" == *"200"* ]]; then
    echo "Matrix notification sent: ${HTTP_CODE}"
else
    echo "ERROR: Matrix API returned: ${HTTP_CODE}" >&2
    exit 1
fi