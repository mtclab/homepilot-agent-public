# Proxmox + Zabbix Deployment Learnings

## Critical Gotchas

### 1. Proxmox VE Node Name ≠ Hostname
- The PVE node name is set during installation and **never** equals the hostname
- Our node is `pve` (not `homepilot` which is the LXC container hostname)
- All PVE API calls must use `/nodes/pve/` not `/nodes/homepilot/`
- **Discovery**: `GET /api2/json/nodes` returns actual node names
- **Mitigation**: Added `PVE_NODE` env var, defaults to `pve`

### 2. PVE API Token ACLs Are Separate from User ACLs
- Creating a token does NOT inherit user permissions
- `monitor@pam!monitoring` had zero ACL entries initially
- Must explicitly assign roles: `PUT /api2/json/access/acl?users=monitor@pam&roles=PVEAuditor&path=/&propagate=1`
- **Monitoring token**: `monitor@pam!monitoring` — PVEAuditor role only
- **Admin token**: `admin@pam!tokenid` — PVEAdmin + Administrator roles
- **Never give Zabbix monitoring token more than PVEAuditor**

### 3. PVE API Token Types: `token` vs `user` in ACL
- Token ACL entries look like: `{"type": "token", "ugid": "admin@pam!tokenid", ...}`
- User ACL entries look like: `{"type": "user", "ugid": "monitor@pam", ...}`
- Tokens inherit their user's perms PLUS their own token-level ACL

### 4. SSL Certificate Mismatch
- PVE uses self-signed cert with CN=`pve.example.com`
- Must add to `/etc/hosts`: `pve.example.local pve.example.com`
- Must use `-k`/`--insecure` for curl, or `verify=False`/`CERT_NONE` for Python
- The Zabbix "Proxmox VE by HTTP" template handles this with `{$PVE.URL.HOST}` macro

### 5. PVE download-url Returns 595 on Wrong Node Name
- `POST /nodes/{WRONG_NODE}/storage/local/download-url` → HTTP 595
- Same for `GET /nodes/{WRONG_NODE}/aplinfo` → HTTP 595
- **Always use the real node name from `/nodes` endpoint**

### 6. PVE Upload Uses `filename` Not `file` Field Name
- Correct: `curl -F "filename=@/path/to/file.tar.zst"`
- Wrong: `curl -F "file=@/path/to/file.tar.zst"` → 400 error
- Upload endpoint: `POST /nodes/{node}/storage/local/upload`

### 7. PVE Can't Reach download.proxmox.com from DMZ
- Template download via `download-url` failed (curl exit code 8)
- **Workaround**: Download to homepilot node first, then upload via multipart POST
- Upload returns UPID task — check status at `/nodes/{node}/tasks/{UPID}/status`

### 8. Template Version Mismatch
- Ubuntu template filename version was `24.04-2` not `24.04-1`
- **Always check aplinfo for exact template name**: `GET /nodes/{node}/aplinfo`
- Our template: `local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst`

### 9. Zabbix Server Interface IP Reverts
- Zabbix server host (ID 10084) interface IP resets to 127.0.0.1 on restart
- **This is normal Zabbix behavior** — internal host uses loopback
- Fix in init script with `fix_zabbix_server_ip()` but may need re-applying after upgrades
- Monitoring still works because passive checks use agent IP, active checks use hostname

### 10. Docker Container Gotchas
- **searxng**: Entry point is `/usr/local/searxng/entrypoint.sh` (not `/usr/bin/`)
- **searxng**: Granian listens on port 8080 (not 8888)
- **n8n**: Alpine-based, must use `#!/bin/sh` and POSIX `[ ]` not `[[ ]]`
- **zabbix-server**: Healthcheck must use `pgrep zabbix_server` (not invalid `-R status`)
- **piper/whisper**: Use `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')"` for healthcheck
- **zabbix-agent2**: Must include Docker bridge networks in `Server=` directive: `172.16.0.0/12,192.168.0.0/16,10.0.0.0/8`
- **zabbix-agent2**: Native apt package, not Docker. Pre-write config before dpkg configure to prevent restart failure

### 11. Two PVE API Tokens — Different Purposes
- `monitor@pam!monitoring` (secret: `CHANGE_ME_pve_token_secret`) — monitoring only, PVEAuditor
- `admin@pam!tokenid` (secret: `REDACTED-TOKEN-PLACEHOLDER`) — admin ops, PVEAdmin+Administrator
- **Never use the admin token for monitoring or in Zabbix templates**

### 12. Matrix Alert Script in Zabbix Server Container
- zabbix-server container has only bash + wget (no python3, no xxd, no curl)
- `matrix_webhook.sh` must escape JSON properly (sed pipeline for quotes/backslashes)
- Use `od -A n -t x1` instead of `xxd` for hex encoding
- Test: `ZABBIX_ALERT_SUBJECT="Test" ZABBIX_ALERT_MESSAGE="Body" /usr/lib/zabbix/alertscripts/matrix_webhook.sh`

## Infrastructure

| Component | Address | Notes |
|-----------|---------|-------|
| Zabbix UI | http://homepilot.example.com:8084 | Admin / (see .env.monitoring) |
| Proxmox VE | https://pve.example.local:8006 | Node: `pve`, CN: `pve.example.com` |
| Homepilot dev | homepilot.example.com | LXC container on Proxmox |
| Matrix | https://matrix.example.com | Room: `:your-room-id:example.com` |

## Proxmox API Quick Reference

```bash
# Authenticate (token auth — no ticket needed)
AUTH="PVEAPIToken=admin@pam!tokenid=REDACTED-TOKEN-PLACEHOLDER"

# List nodes
curl -sk -H "Authorization: $AUTH" "https://pve.example.local:8006/api2/json/nodes"

# List templates
curl -sk -H "Authorization: $AUTH" "https://pve.example.local:8006/api2/json/nodes/pve/storage/local/content?content=vztmpl"

# Download template (if PVE has internet)
curl -sk -X POST -H "Authorization: $AUTH" \
  --data-urlencode "url=http://download.proxmox.com/images/system/ubuntu-24.04-standard_24.04-2_amd64.tar.zst" \
  --data-urlencode "content=vztmpl" \
  "https://pve.example.local:8006/api2/json/nodes/pve/storage/local/download-url"

# Upload template (if PVE can't reach internet)
curl -sk -X POST -H "Authorization: $AUTH" \
  -F "content=vztmpl" \
  -F "filename=@/tmp/ubuntu-24.04-standard_24.04-2_amd64.tar.zst" \
  "https://pve.example.local:8006/api2/json/nodes/pve/storage/local/upload"

# Create LXC
curl -sk -X POST -H "Authorization: $AUTH" \
  -d "vmid=100&hostname=test&ostemplate=local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst&memory=512&swap=256&cores=1&rootfs=local-lvm:8&password=secret&start=0" \
  "https://pve.example.local:8006/api2/json/nodes/pve/lxc"

# Delete LXC
curl -sk -X DELETE -H "Authorization: $AUTH" \
  "https://pve.example.local:8006/api2/json/nodes/pve/lxc/100"

# Manage ACLs
curl -sk -X PUT -H "Authorization: $AUTH" \
  -d "users=monitor@pam&roles=PVEAuditor&path=/&propagate=1" \
  "https://pve.example.local:8006/api2/json/access/acl"

# Remove ACL role
curl -sk -X PUT -H "Authorization: $AUTH" \
  "https://pve.example.local:8006/api2/json/access/acl?users=monitor@pam&roles=Administrator&path=/&propagate=1&delete=1"
```