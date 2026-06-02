# Production Hardening — Zabbix Agent on PVE, SMTP Alerts

## Current Status

### PVE Monitoring (proxmox-ve host, pve.example.local)

- **Template**: Proxmox VE by HTTP (HTTP agent items only)
- **Interface**: HTTP agent, IP pve.example.local, port 10051 (passive check port, but no Zabbix agent installed)
- **Items**: 30+ HTTP agent items (`proxmox.node.*`, `proxmox.lxc.*`, `proxmox.vm.*`)
- **Agent items**: 0 (no Zabbix agent2 on PVE node)
- **Triggers**: API unavailable, high CPU/mem/swap/disk, node offline, kernel/PVE version change, LXC mem
- **TLS**: No encryption configured on PVE host interface

### Zabbix Media Types

| ID | Name | Type | Status |
|----|------|------|--------|
| 1 | Email | SMTP | **Disabled** |
| 4 | Email (HTML) | SMTP | **Disabled** |
| 72 | Matrix Webhook | Script | **Enabled** |

### Zabbix Actions (active)

| ID | Name | Source | Status |
|----|------|--------|--------|
| 7 | Send alerts to Matrix | Triggers | **Enabled** |
| 8 | Auto-register Linux agents | Auto-registration | **Enabled** |

Actions 2, 3, 4, 5, 6 are **disabled** (default Zabbix actions).

---

## 1. Zabbix Agent2 on PVE Node

### Current Gap

PVE host uses HTTP agent items exclusively (PVE API token). No OS-level metrics (process counts, disk I/O, systemd services, swap details) are collected. Adding zabbix-agent2 provides:

- **OS-level metrics**: process counts, disk I/O, systemd service status, open file descriptors
- **Agent-based checks**: `system.cpu.load`, `vm.memory.size`, `vfs.fs.size`, `system.swap`
- **Passive/active checks**: Combined with HTTP agent for comprehensive coverage

### Installation Steps (on PVE node pve.example.local)

```bash
# 1. Install zabbix-agent2
ssh root@pve.example.local
apt update && apt install -y zabbix-agent2

# 2. Configure agent
cat > /etc/zabbix/zabbix_agent2.d/homepilot.conf <<'EOF'
# HomePilot Zabbix Agent2 Configuration
Server=your-server.local
ServerActive=your-server.local:10051
Hostname=proxmox-ve

# TLS (PSK)
TLSConnect=psk
TLSAccept=psk
TLSPSKIdentity=zabbix-agent-pve
TLSPSKFile=/etc/zabbix/zabbix_agent_psk.txt

# Docker plugin (optional — for container metrics on PVE)
# Plugins.Docker.Socket=unix:///var/run/docker.sock
EOF

# 3. Copy PSK file (from dev server)
# First generate on dev: bash monitoring/zabbix/scripts/generate_psk.sh
scp monitoring/zabbix/secrets/zabbix_agent_psk.txt root@pve.example.local:/etc/zabbix/zabbix_agent_psk.txt
chmod 600 /etc/zabbix/zabbix-agent_psk.txt
chown zabbix:zabbix /etc/zabbix/zabbix_agent_psk.txt

# 4. Start agent
systemctl enable --now zabbix-agent2
systemctl status zabbix-agent2

# 5. Verify connectivity (from Zabbix server container)
docker exec zabbix-server zabbix_get -s pve.example.local -k agent.ping \
  --tls-connect psk --tls-pskidentity zabbix-agent-pve --tls-pskfile /run/secrets/zabbix_agent_psk
```

### Zabbix Host Configuration Changes

Add agent interface to existing `proxmox-ve` host:

1. **Configuration → Hosts → proxmox-ve → Interfaces**
   - Add interface: Agent, IP: pve.example.local, Port: 10050
   - Set as default for agent checks

2. **Configuration → Hosts → proxmox-ve → Encryption**
   - Connections from host: PSK
   - PSK identity: `zabbix-agent-pve`
   - PSK: (paste from `zabbix_agent_psk.txt`)

3. **Link additional template**: `Linux by Zabbix agent2`
   - Go to Templates tab → Link `Linux by Zabbix agent2`
   - This adds: CPU, memory, swap, filesystem, process, systemd metrics

4. **Macro overrides** (optional):
   - `{$PVE.MEMORY.PUSE.MAX.WARN}` — already set for PVE

### What This Adds

| Metric Category | Source | Items Added |
|----------------|--------|-------------|
| CPU (load, usage, iowait) | Agent | ~15 items |
| Memory (detailed) | Agent | ~10 items |
| Swap (detailed) | Agent | ~5 items |
| Filesystem (all mounts) | Agent | LLD → ~20 items/disk |
| Processes (by type) | Agent | ~5 items |
| Systemd services | Agent | LLD → varies |
| Network IO | Agent | ~5 items |
| Agent self-monitoring | Agent | ~5 items |

**Key**: HTTP agent items (PVE API) continue working alongside agent items. No conflicts.

---

## 2. SMTP Media Type for Zabbix

### Current State

- **Email** (ID 1) and **Email (HTML)** (ID 4) exist but are **disabled**
- Only **Matrix Webhook** (ID 72) is active for alerts
- No SMTP server configured

### SMTP Configuration

#### Option A: Use Existing SMTP Relay (Recommended for Prod)

If you have access to an SMTP relay (Gmail, SendGrid, Mailgun, etc.):

```bash
# Via Zabbix API or UI: Administration → Media types → Email
# Settings:
SMTP server:     smtp.gmail.com (or your relay)
SMTP port:       587
Security:        STARTTLS
Authentication:  Username/password
Sender email:    zabbix@yourdomain.com
```

#### Option B: Postfix as Local Relay (Self-Hosted)

Add Postfix to Docker Compose for outgoing mail relay:

```yaml
# In docker-compose.monitoring.yml or separate overlay
postfix:
  image: mwader/postfix-relay
  container_name: postfix-relay
  environment:
    POSTFIX_MYHOSTNAME: zabbix.homepilot.local
    POSTFIX_MYDOMAIN: homepilot.local
    POSTFIX_RELAYHOST: "[smtp.gmail.com]:587"
    POSTFIX_SASL_USER: "${SMTP_USER}"
    POSTFIX_SASL_PASSWORD: "${SMTP_PASS}"
  ports:
    - "1025:25"
  networks:
    - monitoring-net
  restart: unless-stopped
```

#### Zabbix SMTP Media Type (API)

```bash
# Enable existing Email media type and configure
# Via Zabbix UI: Administration → Media types → Email

# Or via API (after setting SMTP_PASSWORD secret):
# Update media type ID 1 with:
# - SMTP server: postfix-relay (docker network) or smtp.gmail.com:587
# - SMTP helo: zabbix.homepilot.local
# - SMTP email: zabbix@homepilot.local
# - Security: STARTTLS
# - Authentication: Username/password
# - Username: ${SMTP_USER}
# - Password: ${SMTP_PASSWORD}
```

### Email Alert Action

Create a new action for email alerts:

```bash
# Zabbix UI: Configuration → Actions → Create action
# Name: "Send alerts via Email"
# Conditions: Same as Matrix action (all problems)
# Operations:
#   - Send to user groups: Administrators
#   - Send via: Email
#   - Default message:
#     Subject: {TRIGGER.SEVERITY}: {TRIGGER.NAME}
#     Body: {TRIGGER.NAME}
#           Host: {HOST.NAME}
#           Severity: {TRIGGER.SEVERITY}
#           Time: {EVENT.DATE} {EVENT.TIME}
#           Details: {TRIGGER.DESCRIPTION}
```

### Recommended Setup

For production, configure **both** Matrix webhook AND email media types:

| Priority | Channel | Use Case |
|----------|---------|----------|
| Primary | Matrix Webhook | Real-time alerts in HomePilot Matrix room |
| Secondary | Email | Critical alerts (Disaster/High severity) to on-call |

---

## 3. Summary of Changes Needed

### PVE Agent2 (on pve.example.local)
- [ ] Install `zabbix-agent2` via apt
- [ ] Configure `/etc/zabbix/zabbix_agent2.d/homepilot.conf`
- [ ] Copy PSK file for TLS
- [ ] Enable and start `zabbix-agent2` systemd service
- [ ] Add agent interface (10050) to `proxmox-ve` host in Zabbix
- [ ] Link `Linux by Zabbix agent2` template to `proxmox-ve` host
- [ ] Configure TLS-PSK in Zabbix host encryption settings

### SMTP Alerts
- [ ] Choose SMTP provider (relay service vs self-hosted Postfix)
- [ ] Configure SMTP credentials in Zabbix `.env.monitoring`
- [ ] Enable and update Email media type (ID 1) with SMTP settings
- [ ] Create "Send alerts via Email" action for Disaster/High severity
- [ ] Add user media (email address) to Zabbix admin user

### TLS Reverse Proxy
- [ ] Run `monitoring/caddy/scripts/generate-self-signed-cert.sh hp.local`
- [ ] Deploy Caddy: `docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f monitoring/caddy/docker-compose.tls.yml up -d`
- [ ] For production: set DNS records, update Caddyfile domains, remove static cert paths

### Already Done (This PR)
- [x] Caddyfile for 3-service TLS termination
- [x] Docker Compose overlay for Caddy service
- [x] Self-signed cert generation script
- [x] TLS setup documentation
- [x] PVE Agent2 installation guide
- [x] SMTP media type configuration guide

---

## 4. Zabbix PostgreSQL Password Rotation

### Why

The default Zabbix PG password (`zabbix_pw`) is trivially guessable. An attacker with Docker network access could authenticate to PostgreSQL and exfiltrate or corrupt monitoring data. **Rotate immediately in production.**

### Password Management

The Zabbix PG password is stored in two locations — both must match:

1. **Docker secret file**: `monitoring/zabbix/secrets/zabbix_pg_password.txt` (gitignored)
2. **Environment variable**: `.env` → `ZABBIX_DB_PASSWORD` (gitignored, used for init scripts)

> The `docker-compose.monitoring.yml` uses `_FILE` variants (`POSTGRES_PASSWORD_FILE`, `DB_SERVER_PASSWORD_FILE`, `POSTGRES_PASSWORD_FILE`) that read from the Docker secret, so the env var `ZABBIX_DB_PASSWORD` is **not** passed to containers directly. It exists for scripts and future init automation.

### Rotation Steps

> **Warning**: This requires a brief Zabbix downtime window (PostgreSQL restart needed).

```bash
# 1. Generate a new strong password
NEW_PW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 28)

# 2. Update Docker secret file
echo "$NEW_PW" > monitoring/zabbix/secrets/zabbix_pg_password.txt

# 3. Update .env
sed -i "s/^ZABBIX_DB_PASSWORD=.*/ZABBIX_DB_PASSWORD=$NEW_PW/" .env

# 4. Update PostgreSQL user password (run inside the running container)
docker exec zabbix-postgres psql -U zabbix -c \
  "ALTER USER zabbix WITH PASSWORD '$NEW_PW';"

# 5. Restart Zabbix services to pick up the new secret
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml \
  restart zabbix-server zabbix-web

# 6. Verify Zabbix server can connect (check logs)
docker logs --tail 20 zabbix-server 2>&1 | grep -i "database"
```

### Checklist
- [x] Replace default `zabbix_pw` with strong random password in secret file
- [x] Add `ZABBIX_DB_PASSWORD` to `.env.example` with generation instructions
- [x] Add `ZABBIX_DB_PASSWORD` to `.env.monitoring.example` with generation instructions
- [ ] After deploying: run `ALTER USER` in PostgreSQL to sync the new password
- [ ] Verify Zabbix server reconnects successfully after restart