---
name: homepilot-infra-setup
description: HomePilot full infrastructure setup and troubleshooting — Zabbix, Proxmox, Ollama, nginx, SSH, Docker, VM disk resize, HTTPS/TLS, agent deployment. Trigger on infrastructure, setup, deploy infra, Zabbix, Proxmox, Ollama, nginx, VM resize, HTTPS, TLS, zabbix-agent2, orchestra test, environment bootstrap, provisioning, HP infra, bootstrap infra.
metadata:
  version: "1.0"
  category: infrastructure
  self_learning: false
---

# HomePilot Infrastructure Setup & Troubleshooting Playbook

## What I Do

Set up, configure, and troubleshoot the entire HomePilot infrastructure stack from bare Proxmox to fully operational services. This skill codifies hard-won lessons from real deployment sessions to avoid repeating mistakes.

## When to Use Me

- Setting up HomePilot infrastructure from scratch or after a rebuild
- Configuring Zabbix monitoring on the infrastructure
- Deploying Ollama embedding service for HP v2 knowledge base
- Resizing Proxmox VM disks
- Setting up HTTPS/TLS on nginx reverse proxy
- Installing zabbix-agent2 on Debian/Ubuntu hosts
- Troubleshooting Zabbix server connectivity issues
- Any "orchestra" or full-environment test scenario

## Architecture Overview

```
Proxmox VE Cluster (3 nodes)
├── PVE Node 1 — LXC host (DB, monitor, proxy)
├── PVE Node 2 — hp-core VM (HomePilot v2 + Docker)
└── PVE Node 3 — hp-agent VM (n8n agent stack)

Infrastructure LXCs / VMs
├── hp-db      — PostgreSQL (Zabbix DB, HP v2 DB)
├── hp-monitor  — Zabbix server + agent2
├── hp-proxy    — nginx reverse proxy (HTTPS termination)
├── hp-core     — HomePilot v2 + Docker + Ollama socat bridge
└── hp-agent    — n8n agent stack

Key Service Ports
├── 443     — HTTPS entry point (nginx on hp-proxy)
├── 8000    — HP v2 API (hp-core)
├── 80      — Zabbix UI (hp-monitor) → proxied via /zabbix/
├── 11434   — Ollama API (localhost only on hp-core)
├── 11435   — Ollama socat bridge (0.0.0.0 on hp-core, for containers)
├── 10050   — zabbix-agent2 (all monitored hosts)
└── 10051   — zabbix-server trapper (hp-monitor)
```

## Critical Lessons Learned (Avoid These Mistakes)

### Lesson 1: Zabbix Server DB Host Must Point to the DB Server

**Mistake**: Zabbix defaults `DBHost=localhost` — this fails when PostgreSQL runs on a separate host.

**Correct**: Set `DBHost` to the actual DB server IP, then restart:
```bash
sudo sed -i 's/^DBHost=.*/DBHost=<DB_HOST_IP>/' /etc/zabbix/zabbix_server.conf
sudo systemctl restart zabbix-server
```

### Lesson 2: Zabbix Setup Wizard Requires php-pgsql

**Mistake**: Default Zabbix PHP only includes MySQL driver. Setup wizard fails with "Unsupported database type".

**Correct** (Ubuntu 24.04):
```bash
sudo apt-get install -y php8.3-pgsql
sudo locale-gen en_US.UTF-8   # Also needed — Zabbix UI fails without this locale
sudo systemctl restart apache2  # or php8.3-fpm
```

### Lesson 3: Zabbix Server Host Interface Must Use Real IP

**Mistake**: Default "Zabbix server" host uses `127.0.0.1`. If the agent listens on a different IP, it shows "unavailable".

**Fix via API**:
```bash
# Login and get auth token, then update interface IP
curl -s -X POST http://<ZABBIX_HOST>/zabbix/api_jsonrpc.php \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"hostinterface.update","params":{"interfaceid":"1","ip":"<REAL_IP>"},"auth":"<TOKEN>","id":2}'
```

### Lesson 4: PVE Bare-Metal Hosts Reject SSH

**Problem**: PVE hosts have `PermitRootLogin=no` and no authorized keys deployed by default. You cannot SSH to them.

**Workaround**: Use Proxmox MCP API for all PVE operations. For Zabbix monitoring, use HTTP agent items polling the PVE API, NOT zabbix-agent2.

**Cannot do**: Install zabbix-agent2 on PVE hosts without console/VNC access.

### Lesson 5: VM Disk Resize Requires stop+start, NOT Reboot

**Mistake**: Running `reboot` inside the VM — QEMU doesn't see the new disk size.

**Correct procedure**:
```bash
# 1. Resize via Proxmox API (can be done while VM is running for scsi disks)
#    proxmox_proxmox_resize_vm(node="pve2", vmid=200, disk="scsi0", size="20G", confirm=true)

# 2. Stop VM completely (not reboot!)
#    proxmox_proxmox_shutdown_vm(node="pve2", vmid=200, confirm=true)
#    Wait for shutdown, then:
#    proxmox_proxmox_start_vm(node="pve2", vmid=200, confirm=true)

# 3. Inside VM: grow partition and resize filesystem
ssh root@<VM_IP> 'growpart /dev/sda 1 && resize2fs /dev/sda1 && df -h /'
```

### Lesson 6: Ollama Embedding Needs Socat Bridge for Container Access

**Problem**: HP v2 runs in Docker. Ollama listens on `localhost:11434`. Containers can't reach host `localhost`.

**Solution** — Socat bridge on port 11435:
```bash
# On the Ollama host
cat > /etc/systemd/system/ollama-socat.service << 'EOF'
[Unit]
Description=Socat proxy for Ollama (0.0.0.0 to localhost)
After=network.target

[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:11435,fork,reuseaddr,bind=0.0.0.0 TCP:localhost:11434
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ollama-socat
```

**HP v2 container env vars** (set in docker-compose or Dockerfile):
```
HP_EMBEDDING_SERVICE_URL=http://host.docker.internal:11435/api/embeddings
HP_EMBEDDING_MODEL=nomic-embed-text
```

**If using a remote/cloud Ollama** — establish an SSH tunnel first:
```bash
ssh -o StrictHostKeyChecking=no -i <TUNNEL_KEY> \
  -R 11434:<OLLAMA_HOST>:11434 -N -f root@<OLLAMA_PROXY_HOST>
```

⚠️ SSH tunnels are ephemeral — must be re-established after host/workspace restart.

### Lesson 7: zabbix-agent2 Server IP Must Match Zabbix Server

**Mistake**: Agent config `Server=127.0.0.1` — won't accept connections from the Zabbix server.

**Correct** (on every monitored host):
```bash
sudo sed -i 's/^Server=.*/Server=<ZABBIX_SERVER_IP>/' /etc/zabbix/zabbix_agent2.conf
sudo sed -i 's/^ServerActive=.*/ServerActive=<ZABBIX_SERVER_IP>/' /etc/zabbix/zabbix_agent2.conf
sudo systemctl restart zabbix-agent2
```

### Lesson 8: HTTPS on nginx Proxy — Self-Signed Cert

```bash
# On the proxy host
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/homepilot.key \
  -out /etc/ssl/certs/homepilot.crt \
  -subj "/CN=homepilot.local/O=HomePilot"

# Key nginx config points:
# - listen 443 ssl; ssl_certificate/ssl_certificate_key paths
# - ssl_protocols TLSv1.2 TLSv1.3
# - add_header Strict-Transport-Security "max-age=31536000"
# - server 80 { return 301 https://$host$request_uri; }
# - location /zabbix/ { proxy_pass http://<ZABBIX_HOST>:80/zabbix/; }
# - location / { proxy_pass http://<HP_CORE_HOST>:8000; }

nginx -t && systemctl reload nginx
```

## Step-by-Step: Full Infrastructure Bootstrap

### Phase 1: Proxmox Prerequisites
1. Verify PVE cluster health via `proxmox_proxmox_cluster_status`
2. Create snapshots before changes via `proxmox_proxmox_create_snapshot`
3. Verify all VMs/LXCs running via `proxmox_proxmox_cluster_resources`

### Phase 2: Zabbix Setup
1. Install Zabbix server + PostgreSQL + agent2 on monitor host
2. Install `php<version>-pgsql` and generate `en_US.UTF-8` locale
3. Import Zabbix SQL schema into PostgreSQL on DB host
4. Set `DBHost=<DB_HOST_IP>` in `zabbix_server.conf`
5. Start zabbix-server, zabbix-agent2, nginx/php-fpm
6. Run Zabbix setup wizard in browser
7. Change Admin password

### Phase 3: Zabbix Host Registration
1. Create "HomePilot Infrastructure" host group via API
2. Get "Linux by Zabbix agent" template ID via API
3. Create each host with correct IP interface
4. Fix Zabbix server host interface IP (Lesson 3)

### Phase 4: Install zabbix-agent2 on All Hosts
```bash
# On each LXC/VM:
wget https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb
sudo apt update && sudo apt install -y zabbix-agent2
# Configure Server/ServerActive (Lesson 7)
sudo systemctl enable --now zabbix-agent2
```

**EXCEPTION**: PVE bare-metal hosts — cannot install agent (Lesson 4). Use API monitoring instead.

### Phase 5: Ollama Embedding
1. Set up SSH tunnel to Ollama backend (if remote)
2. Create socat bridge systemd service (Lesson 6)
3. Set HP v2 container env vars

### Phase 6: HTTPS/TLS on nginx
1. Generate self-signed cert (Lesson 8)
2. Configure nginx with HTTPS + redirect
3. Test and reload

## Verification Checklist

```bash
# 1. Zabbix agents responding
for IP in <MONITOR_HOSTS>; do
  zabbix_get -s $IP -k system.hostname  # Should return hostname
done

# 2. HP v2 health
curl -s http://<HP_CORE_HOST>:8000/health

# 3. HTTPS proxy
curl -sk https://<PROXY_HOST>/health
curl -sI http://<PROXY_HOST>/ | head -3  # Should show 301 redirect

# 4. Ollama embedding dimension
curl -s http://<OLLAMA_HOST>:11435/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"test"}'

# 5. Zabbix API login
curl -s -X POST http://<ZABBIX_HOST>/zabbix/api_jsonrpc.php \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"user.login","params":{"username":"Admin","password":"<PASSWORD>"},"id":1}'
```

## Examples

### Example 1: Quick zabbix-agent2 Install on New Host
```bash
ssh root@<HOST> 'wget -q https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-2+ubuntu24.04_all.deb && dpkg -i zabbix-release_7.0-2+ubuntu24.04_all.deb && apt update && apt install -y zabbix-agent2 && sed -i "s/^Server=.*/Server=<ZABBIX_IP>/" /etc/zabbix/zabbix_agent2.conf && sed -i "s/^ServerActive=.*/ServerActive=<ZABBIX_IP>/" /etc/zabbix/zabbix_agent2.conf && systemctl enable --now zabbix-agent2 && echo DONE'
```

### Example 2: Re-establish Ollama Tunnel After Restart
```bash
ssh -o StrictHostKeyChecking=no -i <TUNNEL_KEY> \
  -R 11434:<OLLAMA_BACKEND>:11434 -N -f root@<OLLAMA_PROXY_HOST>
# Then restart socat if not running:
ssh root@<OLLAMA_PROXY_HOST> 'systemctl restart ollama-socat'
```

### Example 3: Resize Proxmox VM Disk
```bash
# 1. Resize via API
#    proxmox_proxmox_resize_vm(node=<PVE_NODE>, vmid=<ID>, disk="scsi0", size="<NEW_SIZE>", confirm=true)

# 2. If VM doesn't see new size, stop+start (NOT reboot)
#    proxmox_proxmox_shutdown_vm(node=<PVE_NODE>, vmid=<ID>, confirm=true)
#    proxmox_proxmox_start_vm(node=<PVE_NODE>, vmid=<ID>, confirm=true)

# 3. Inside VM: grow partition and resize filesystem
ssh root@<VM_IP> 'growpart /dev/sda 1 && resize2fs /dev/sda1 && df -h /'
```

## Failure Modes

| Failure | Cause | Fix |
|---------|-------|-----|
| Zabbix setup wizard 500 error | Missing `php-pgsql` | `apt install php<ver>-pgsql && systemctl restart php-fpm` |
| Zabbix UI locale error | Missing `en_US.UTF-8` locale | `locale-gen en_US.UTF-8` |
| Zabbix server DB connection refused | `DBHost=localhost` instead of DB server IP | Edit `zabbix_server.conf`, restart server |
| Zabbix agents "unavailable" | Wrong `Server=` IP in agent config | Must point to Zabbix server IP |
| PVE SSH auth denied | `PermitRootLogin=no`, no key deployed | Use Proxmox MCP API only |
| VM disk resize not visible | Used reboot instead of stop+start | Must stop+start VM from Proxmox |
| Ollama embedding 404 from container | Port 11434 only on localhost | Use socat bridge on 11435 |
| zabbix_get "connection reset" | Agent `Server=` points to wrong IP | Must match Zabbix server IP |
| Nginx 502 on /zabbix/ | Zabbix server not running on monitor host | `systemctl restart zabbix-server zabbix-agent2 nginx php-fpm` |
| MCP config changes not taking effect | MCP process needs restart, not hot-reload | Restart the MCP process after config edits |

## Proxmox API Notes

- All PVE operations MUST go through Proxmox MCP tools (no SSH to PVE hosts)
- `proxmox_proxmox_node_execute` has a known validation bug — cannot run shell commands on PVE hosts
- PVE hosts reject SSH key auth and password auth
- Use `node="pve1"`, `node="pve2"`, or `node="pve3"` in MCP calls