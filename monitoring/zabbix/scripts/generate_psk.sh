#!/usr/bin/env bash
# Generate PSK files for Zabbix TLS/PSK encryption
# Creates separate PSK files for zabbix-server and zabbix-agent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SECRETS_DIR="${SCRIPT_DIR}/../secrets"
mkdir -p "$SECRETS_DIR"

generate_psk() {
  local name="$1"
  local identity="$2"
  local outfile="${SECRETS_DIR}/${name}_psk.txt"

  openssl rand -hex 32 > "$outfile"
  chmod 600 "$outfile"

  echo "[OK] ${outfile} — identity: ${identity}"
  echo "     PSK length: $(wc -c < "$outfile" | tr -d ' ') bytes"
}

echo "=== Generating Zabbix TLS/PSK keys ==="
echo ""

generate_psk "zabbix_server" "zabbix-server"
generate_psk "zabbix_agent" "$(hostname -s 2>/dev/null || echo 'CHANGE_ME_hostname')"

echo ""
echo "=== Done ==="
echo "Files are in: ${SECRETS_DIR}/"
echo ""
echo "IMPORTANT:"
echo "  - These files are gitignored (never commit secrets)"
echo "  - Set ZBX_TLSPSKIDENTITY in .env.monitoring if hostname detection failed"
echo "  - Add PSK identity/key in Zabbix UI: Configuration → Hosts → Encryption"