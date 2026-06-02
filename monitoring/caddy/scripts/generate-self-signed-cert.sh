#!/usr/bin/env bash
# Generate self-signed TLS certificate for development
# Production: Use Let's Encrypt (Caddy handles this automatically)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/../certs"
mkdir -p "$CERTS_DIR"

DOMAIN="${1:-hp.local}"
ALT_NAMES="${DOMAIN}"
ALT_NAMES+=",zabbix.${DOMAIN}"
ALT_NAMES+=",n8n.${DOMAIN}"
ALT_NAMES+=",localhost"
ALT_NAMES+=",your-server.local"

echo "=== Generating self-signed TLS certificate ==="
echo "Domain: ${DOMAIN}"
echo "SANs: ${ALT_NAMES}"
echo ""

# Generate private key
openssl genrsa -out "${CERTS_DIR}/tls.key" 2048 2>/dev/null

# Generate CSR with SANs
cat > "${CERTS_DIR}/openssl.cnf" <<EOF
[req]
distinguished_name = req_dn
x509_extensions = v3_req
prompt = no

[req_dn]
CN = ${DOMAIN}

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = digitalSignature,keyEncipherment

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = zabbix.${DOMAIN}
DNS.3 = n8n.${DOMAIN}
DNS.4 = localhost
IP.1 = your-server.local
IP.2 = 127.0.0.1
EOF

# Generate self-signed cert (valid 365 days)
openssl req -new -x509 \
  -key "${CERTS_DIR}/tls.key" \
  -out "${CERTS_DIR}/tls.crt" \
  -days 365 \
  -config "${CERTS_DIR}/openssl.cnf" \
  2>/dev/null

chmod 644 "${CERTS_DIR}/tls.crt"
chmod 600 "${CERTS_DIR}/tls.key"

echo "[OK] Certificate generated:"
echo "     ${CERTS_DIR}/tls.crt"
echo "     ${CERTS_DIR}/tls.key"
echo ""
echo "=== Production Notes ==="
echo "For production, replace self-signed cert with ACME (Let's Encrypt):"
echo "  1. Set real DNS A records for your domain"
echo "  2. Edit Caddyfile — replace hp.local with your domain"
echo "  3. Change Caddy TLS directive from static certs to auto-HTTPS"
echo "  4. Caddy will auto-provision and renew Let's Encrypt certs"
echo ""
echo "Caddyfile change for production (single domain):"
echo '  hp.example.com {'
echo '      reverse_proxy homepilot:8000'
echo '      # No tls directive needed — Caddy auto-provisions'
echo '  }'