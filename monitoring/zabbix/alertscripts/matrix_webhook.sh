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

MD_BODY="${ICON} **[${SEVERITY}] ${SUBJECT}**\n\n${MESSAGE}"
if [[ -n "$ZABBIX_URL" ]]; then
    MD_BODY="${MD_BODY}\n\n[View in Zabbix](${ZABBIX_URL})"
fi

# Convert markdown to HTML for formatted_body
HTML_BODY=$(printf '%s' "$MD_BODY" | python3 -c '
import html, re, sys

text = sys.stdin.read()

out = text
out = re.sub(r"```(\w*)\n(.*?)\n```", lambda m: "<pre><code>" + html.escape(m.group(2)) + "</code></pre>", out, flags=re.DOTALL)
out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href=\"\2\">\1</a>", out)
out = re.sub(r"^### (.+)$", r"<h3>\1</h3>", out, flags=re.MULTILINE)
out = re.sub(r"^## (.+)$", r"<h2>\1</h2>", out, flags=re.MULTILINE)
out = re.sub(r"^# (.+)$", r"<h1>\1</h1>", out, flags=re.MULTILINE)
out = out.replace("\n", "<br>\n")
print(out)
')

# Strip markdown for plain-text body
PLAIN_BODY=$(printf '%s' "$MD_BODY" | sed 's/\*\*//g; s/\*//g; s/`//g; s/\[([^]]*)]([^)]*)/\1/g' | sed 's/```//g')

TXN_ID="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"

URL="${SERVER}/_matrix/client/v3/rooms/${ROOM_ID}/send/m.room.message/${TXN_ID}"

# Build JSON payload with both plain body and formatted HTML body
ESCAPED_PLAIN=$(printf '%s' "$PLAIN_BODY" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g' | tr '\n' ' ')
ESCAPED_HTML=$(printf '%s' "$HTML_BODY" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g' | tr '\n' ' ')

PAYLOAD=$(printf '{"msgtype":"m.notice","body":"%s","format":"org.matrix.custom.html","formatted_body":"%s"}' "$ESCAPED_PLAIN" "$ESCAPED_HTML")

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