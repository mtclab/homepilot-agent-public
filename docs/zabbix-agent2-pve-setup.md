# Zabbix Agent2 on Proxmox VE — Setup Guide

## Prerequisites
- PVE node console access (required — API `/nodes/{node}/execute` needs root@pam user, not token auth)
- Zabbix server already running at your-server.local:10051

## Installation (on PVE node)

```bash
# SSH into PVE node as root
ssh root@pve.example.local

# Install zabbix-agent2
apt-get update && apt-get install -y zabbix-agent2

# Configure agent
cat > /etc/zabbix/zabbix_agent2.conf << 'CONF'
Server=your-server.local
ServerActive=your-server.local
Hostname=proxmox-ve
ListenPort=10050
TLSConnect=psk
TLSAccept=psk
TLSPSKIdentity=PSK-pve
TLSPSKFile=/etc/zabbix/psk/pve.psk
AllowKey=system.run[*]
Plugins.Docker.ListenPort=0
CONF

# Generate PSK
mkdir -p /etc/zabbix/psk
openssl rand -hex 32 > /etc/zabbix/psk/pve.psk
chmod 600 /etc/zabbix/psk/pve.psk

# Enable and start
systemctl enable zabbix-agent2
systemctl start zabbix-agent2
```

## Zabbix UI Configuration

1. Go to Configuration → Hosts → proxmox-ve
2. Add interface: Agent → pve.example.local:10050
3. Link template: `Linux by Zabbix agent2`
4. Already linked: `Template PVE Security`
5. Set PSK in Encryption tab:
   - PSK identity: `PSK-pve`
   - PSK: (value from /etc/zabbix/psk/pve.psk)

## Verification
```bash
# On PVE node
zabbix_agent2 -t agent.ping
zabbix_agent2 -t system.hostname
```

## Troubleshooting
- Check logs: `journalctl -u zabbix-agent2 -f`
- Test connection: `zabbix_get -s pve.example.local -p 10050 -k agent.ping`
