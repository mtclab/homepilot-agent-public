---
name: zabbix-setup
description: Deploy and configure Zabbix 7.0 monitoring for HomePilot infrastructure. Trigger on zabbix, monitoring, alert, trigger, dashboard, host, template, agent2, autoregistration, matrix webhook. Covers Zabbix server deploy, agent2 install, host registration, template linking, trigger/action creation, and Matrix alert routing.
---

# Zabbix Setup

Deploy and configure Zabbix 7.0 monitoring for the HomePilot homelab.

## When to Use

- Deploying Zabbix 7.0 stack (Docker Compose overlay)
- Installing zabbix-agent2 on VMs/LXCs
- Registering hosts and linking templates
- Creating triggers, actions, and dashboards
- Configuring Matrix webhook for alert notifications
- Setting up autoregistration rules
- Troubleshooting monitoring gaps

## Infrastructure

| Host | IP | Agent | Monitored Via |
|------|-----|-------|---------------|
| Zabbix Server | zabbix.example.local | Docker | Self-monitoring |
| dev server | your-server.local | agent2 + Docker plugin | Zabbix agent |
| PVE node | pve.example.local | HTTP agent template | PVE API polling |
| ProxMox MCP | mcp.example.local | agent2 | Zabbix agent |

### Ports
- Zabbix Web UI: `http://zabbix.example.local:8084`
- Zabbix Server: 10051 (trapper)
- Zabbix Agent: 10050 (on monitored hosts)

## Deployment Steps

### 1. Start Zabbix Stack
```bash
# Deploy monitoring overlay
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Verify
curl -s http://localhost:8084/api_jsonrpc.php \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"apiinfo.version","id":1}'
```

### 2. Initialize Zabbix
```bash
# Run init script (creates admin password, hosts, templates, media types)
./scripts/init-zabbix.sh
```

### 3. Install Agent2 on VMs
```bash
# On each monitored host
./scripts/install-zabbix-agent2.sh  # installs zabbix-agent2, configures for Docker plugin
```

### 4. Register Hosts (via Zabbix API)
```python
# Create host group
zabbix_hostgroup_create(name="HomePilot Infrastructure")

# Register dev server
zabbix_host_create(
    host="homepilot-dev",
    groups=[{"groupid": "<groupid>"}],
    interfaces=[{"type":1, "main":1, "useip":1, "ip":"your-server.local", "port":"10050"}]
)
```

### 5. Configure Matrix Alert Routing
```bash
# Zabbix alert scripts are in monitoring/zabbix/alertscripts/
# matrix_webhook.sh sends alerts to Matrix room
# Configure in Zabbix UI: Administration → Media types → Script
```

## Key Files
```
monitoring/zabbix/
├── alertscripts/
│   ├── matrix_webhook.sh      # Bash Matrix notifier (container-safe)
│   └── matrix_webhook.py      # Python fallback with severity icons
├── secrets/
│   ├── zabbix_pg_password     # PostgreSQL password
│   ├── zabbix_server_psk      # PSK for encrypted agent communication
│   └── zabbix_agent_psk       # Agent-side PSK
└── zabbix_agent2.conf         # Agent2 config with Docker plugin
```

## Monitoring Templates

| Template | Target |
|----------|--------|
| Linux by Zabbix agent | All Linux hosts |
| Docker | Hosts running containers |
| Proxmox VE by HTTP | PVE nodes (API polling) |
| HomePilot Health | HomePilot backend (HTTP health) |

## Alert Flow

```
Zabbix trigger fires
  → Action evaluates conditions
  → Script media type (matrix_webhook.sh)
  → POST to Matrix room
  → Alert delivered to !room:example.com
```

## Troubleshooting

- **Zabbix web not loading**: Check `docker compose ps zabbix-web`, verify PostgreSQL is running
- **Agent not connecting**: Check `zabbix_agent2.conf` ServerActive points to Zabbix server IP
- **No Docker metrics**: Ensure `docker.sock` is mounted in agent2 config, Docker plugin enabled
- **Matrix alerts not delivered**: Check `matrix_webhook.sh` has correct `MATRIX_ROOM_ID` and `MATRIX_ACCESS_TOKEN`
- **PVE monitoring gaps**: Verify PVE API token in Zabbix macro `{$PVE_TOKEN}`