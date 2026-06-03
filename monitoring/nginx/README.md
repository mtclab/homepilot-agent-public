# TLS Reverse Proxy — HomePilot Stack

Caddy-based TLS termination for all HomePilot services.

## Architecture

```
                    ┌──────────────┐
                    │   Caddy      │
                    │   :443/:80   │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────────┐
            │              │                  │
    ┌───────▼──────┐ ┌─────▼──────┐  ┌──────▼──────┐
    │ HomePilot    │ │ Zabbix Web │  │ n8n         │
    │ :8000        │ │ :8084      │  │ :5678       │
    └──────────────┘ └────────────┘  └─────────────┘
```

Caddy handles:
- TLS termination (auto-HTTPS with Let's Encrypt or self-signed)
- HTTP→HTTPS redirect
- Reverse proxy to backend services
- Basic auth headers (optional)

## Quick Start

### Self-Signed (Development)

```bash
# 1. Generate self-signed cert
bash scripts/generate-self-signed-cert.sh

# 2. Start Caddy
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d caddy
```

### Let's Encrypt (Production)

```bash
# 1. Set DNS A records for your domain pointing to homepilot.example.com
# 2. Edit monitoring/caddy/Caddyfile — replace homepilot.example.com with your domain
# 3. Set env vars:
export DOMAIN=homepilot.example.com
export ZABBIX_DOMAIN=zabbix.example.com
export N8N_DOMAIN=n8n.example.com

# 4. Start Caddy
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d caddy
```

## Service Mappings

| Service | Internal | Caddy Route | Production Domain |
|---------|----------|-------------|-------------------|
| HomePilot API | `:8000` | `/` | `homepilot.example.com` |
| Zabbix Web | `:8084` | `/` | `zabbix.example.com` |
| n8n | `:5678` | `/` | `n8n.example.com` |

## Zabbix Agent2 Access

Zabbix agent connections still use direct IP (port 10050/10051) — not proxied through Caddy. TLS-PSK encrypts agent traffic directly.

## Cert Rotation

Self-signed certs expire in 365 days. For production, Caddy handles cert renewal automatically via ACME (Let's Encrypt).