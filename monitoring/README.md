# HomePilot Monitoring Stack

Zabbix 7.0 — single-product monitoring for the entire Proxmox homelab.

## Architecture

```
MONITORING VM (3 Docker containers):
  - zabbix-server  (collector, processor, alerter)
  - zabbix-web     (UI, API, dashboards)
  - zabbix-postgres (database)

PROXMOX HOST:
  - No agent. Zabbix polls Proxmox API via "Proxmox VE by HTTP" template.
  - Auto-discovers nodes, VMs, LXCs, storage.

APPLICATION VMs:
  - zabbix-agent2 (apt package, ~30MB RAM)
  - Docker plugin enabled (auto-discovers containers)
  - Auto-registers with Zabbix server on boot

ALERTING:
  - Zabbix triggers → script media type → Matrix room

MCP INTEGRATION:
  - Zabbix MCP server (mpeirone/zabbix-mcp-server) provides 3 tools:
    zabbix_api, zabbix_api_docs, zabbix_api_list
  - Opencode agents can query hosts, problems, triggers, history
  - READ_ONLY mode by default (safe for planning agents)
```

## Quick Start

### 1. Create environment file

```bash
cd /path/to/homepilot-agent
cp monitoring/zabbix/.env.monitoring.example .env.monitoring
# Edit .env.monitoring with your passwords, tokens, Proxmox URL, etc.
```

### 2. Start the monitoring stack

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### 3. Initialize Zabbix

```bash
# This script: waits for UI, changes admin password, creates hosts/media types/actions
# Ongoing config should use the Zabbix MCP server, not this script
bash scripts/init-zabbix.sh
```

For subsequent configuration changes (adding hosts, templates, macros, actions), use the **Zabbix MCP server** rather than re-running init:

```bash
# The MCP server provides 3 tools covering the entire Zabbix API:
# zabbix_api       — execute any Zabbix API method (host.create, trigger.get, etc.)
# zabbix_api_docs  — get documentation for any API method
# zabbix_api_list  — discover available API objects and methods
#
# Example via opencode agents:
#   "Use zabbix_api to create a new host with the Linux template"
#   "Use zabbix_api to list all current problems"
#   "Use zabbix_api_docs to see what parameters host.create accepts"
```

### 4. Configure Proxmox API token

On the Proxmox host:
```bash
pvesh create /access/users/monitor@pam/token --privsep 0 --expire-unix 0
# Or via UI: Datacenter → Permissions → API Tokens
# Role: PVEAuditor on / path
```

Then set the token in `.env.monitoring` and re-run `init-zabbix.sh` (or update macros in Zabbix UI).

### 5. Install agent2 on VMs

```bash
# On each VM:
bash scripts/install-zabbix-agent2.sh <ZABBIX_SERVER_IP> <HOSTNAME>
# The script auto-detects Docker and allows Docker bridge networks
```

### 6. Configure Zabbix MCP server (opencode)

Add to `opencode.json`:
```json
{
  "mcp": {
    "zabbix": {
      "type": "local",
      "enabled": true,
      "command": ["zabbix-mcp"],
      "env": {
        "ZABBIX_URL": "http://YOUR_ZABBIX_HOST:8084",
        "ZABBIX_USER": "Admin",
        "ZABBIX_PASSWORD": "your-password",
        "READ_ONLY": "true",
        "ZABBIX_MCP_TRANSPORT": "stdio"
      },
      "timeout": 30000
    }
  }
}
```

Or use API token auth (recommended):
```json
{
  "env": {
    "ZABBIX_URL": "http://YOUR_ZABBIX_HOST:8084",
    "ZABBIX_TOKEN": "your-api-token",
    "READ_ONLY": "true",
    "ZABBIX_MCP_TRANSPORT": "stdio"
  }
}
```

## Monitoring Stack Details

| Component | Version | Port | Purpose |
|-----------|---------|------|---------|
| zabbix-server | 7.0 | 10051 | Collector, alerter |
| zabbix-web | 7.0 | 8084 | Web UI, dashboards |
| zabbix-postgres | 16 | 5432 | Database |
| zabbix-agent2 | 7.0 | 10050 | Per-VM agent (native apt) |

## What Gets Monitored

| Target | Method | What |
|--------|--------|------|
| Proxmox hosts | HTTP API (agentless) | CPU, RAM, disk, network, VM/LXC status |
| VMs | agent2 (apt) | CPU, RAM, disk, network, processes, logs |
| Docker containers | agent2 Docker plugin | Container status, resource usage, restart counts |
| LXCs | Proxmox API (agentless) | CPU, RAM, disk, network |
| Services | HTTP/ICMP checks | HomePilot /health, n8n, SearXNG, etc. |

## Adding a New VM

1. Install agent2: `bash scripts/install-zabbix-agent2.sh <ZABBIX_SERVER_IP>`
2. Agent auto-registers with Zabbix (Linux + Docker metadata)
3. Zabbix links appropriate templates automatically
4. Metrics appear in dashboards within 2 minutes

## Troubleshooting

```bash
# Check Zabbix server logs
docker logs zabbix-server

# Check agent2 status on a VM
sudo systemctl status zabbix-agent2
sudo tail -f /var/log/zabbix/zabbix_agent2.log

# Check agent can reach server
zabbix_get -s <AGENT_IP> -k agent.ping

# Test Matrix webhook from container
docker exec zabbix-server ZABBIX_ALERT_SUBJECT="Test" \
  ZABBIX_ALERT_MESSAGE="Test alert" \
  /usr/lib/zabbix/alertscripts/matrix_webhook.sh
```