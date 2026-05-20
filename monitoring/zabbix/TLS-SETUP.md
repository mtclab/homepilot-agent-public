# Zabbix TLS/PSK Setup

Zabbix supports encrypted communication between server and agents using TLS with Pre-Shared Keys (PSK). This avoids the overhead of certificate management while providing encryption and identity verification.

## Overview

```
Zabbix Server (10051) ←→ Zabbix Agent2 (10050)
     PSK: zabbix-server      PSK: zabbix-agent-<hostname>
     Identity: server        Identity: agent-<hostname>
```

All connections use TLS-PSK (no certificates required).

## 1. Generate PSK Files

Run the generation script:

```bash
bash monitoring/zabbix/scripts/generate_psk.sh
```

This creates:
- `monitoring/zabbix/secrets/zabbix_server_psk.txt` — server-side PSK
- `monitoring/zabbix/secrets/zabbix_agent_psk.txt` — agent-side PSK

Both are 32-byte hex strings (64 hex characters), readable only by owner (chmod 600).

The files are gitignored — **never commit them**.

## 2. Configure Docker Compose

The `docker-compose.monitoring.yml` already includes the TLS environment variables and secret mounts. After generating PSK files:

```bash
# Validate config
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml config
```

Then restart the monitoring stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

## 3. Configure Zabbix Agent2 (Native Install on VMs)

For each VM running `zabbix-agent2` as an apt package:

### 3a. Copy the PSK file

```bash
# On the VM, create the PSK file
sudo mkdir -p /etc/zabbix
sudo tee /etc/zabbix/zabbix_agent_psk.txt <<< "$(cat monitoring/zabbix/secrets/zabbix_agent_psk.txt)"
sudo chmod 600 /etc/zabbix/zabbix_agent_psk.txt
sudo chown zabbix:zabbix /etc/zabbix/zabbix_agent_psk.txt
```

### 3b. Edit agent config

Edit `/etc/zabbix/zabbix_agent2.conf` (or drop a file in `/etc/zabbix/zabbix_agent2.d/`):

```ini
# TLS connection to server
TLSConnect=psk
TLSAccept=psk
TLSPSKIdentity=zabbix-agent-<hostname>
TLSPSKFile=/etc/zabbix/zabbix_agent_psk.txt
```

Replace `<hostname>` with the actual hostname (must match what you enter in Zabbix UI).

### 3c. Restart agent

```bash
sudo systemctl restart zabbix-agent2
sudo systemctl status zabbix-agent2
```

### 3d. Verify

```bash
# From Zabbix server container
zabbix_get -s <AGENT_IP> -k agent.ping --tls-connect psk --tls-pskidentity "zabbix-agent-<hostname>" --tls-pskfile /run/secrets/zabbix_agent_psk
```

## 4. Add PSK to Zabbix Host Configuration (Web UI)

For each host that uses TLS-PSK:

1. Go to **Configuration → Hosts**
2. Click the host name
3. Switch to the **Encryption** tab
4. Set:
   - **Connections from host**: PSK
   - **PSK identity**: `zabbix-agent-<hostname>` (must match agent's `TLSPSKIdentity`)
   - **PSK**: paste the 64-character hex string from `monitoring/zabbix/secrets/zabbix_agent_psk.txt`
5. Click **Update**

## 5. Using install-zabbix-agent2.sh with TLS

When using the agent install script, pass the PSK identity and file:

```bash
bash scripts/install-zabbix-agent2.sh <SERVER_IP> <HOSTNAME> --psk-identity zabbix-agent-<hostname> --psk-file /path/to/zabbix_agent_psk.txt
```

## 6. Server-to-Server PSK

The `zabbix-server` service uses its own PSK (`zabbix_server_psk`) for active checks and proxy communication. This is configured automatically via Docker secrets in `docker-compose.monitoring.yml`.

## Security Notes

- PSK files are **gitignored** (`monitoring/zabbix/secrets/*_psk.txt`)
- Each agent should have a **unique PSK identity** (typically `zabbix-agent-<hostname>`)
- PSK identity strings are sent in **cleartext** during TLS handshake — do not embed secret info in identity strings
- For production, consider TLS with certificates (x509) instead of PSK for stronger identity verification
- Rotate PSKs periodically — regenerate and update both agent config and Zabbix UI
- The `generate_psk.sh` script overwrites existing PSK files — schedule regeneration carefully

## Troubleshooting

```bash
# Check agent TLS errors
sudo tail -f /var/log/zabbix/zabbix_agent2.log | grep -i tls

# Test from server with PSK
docker exec zabbix-server zabbix_get \
  -s <AGENT_IP> -k agent.ping \
  --tls-connect psk \
  --tls-pskidentity "zabbix-agent-$(hostname)" \
  --tls-pskfile /run/secrets/zabbix_agent_psk

# Common errors:
# - "PSK identity mismatch" → identity in agent config doesn't match Zabbix UI
# - "TLS handshake failed" → wrong PSK key or file permissions
# - "connection refused" → agent not listening or firewall blocking
```