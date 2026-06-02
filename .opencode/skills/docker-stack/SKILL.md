---
name: docker-stack
description: Manage HomePilot Agent Docker Compose stack. Trigger on docker, compose, container, stack, n8n, zabbix, searxng, radicale, LLM, whisper, piper. Covers starting/stopping services, Docker secrets, health checks, logs, GPU assignment, compose profiles.
---

# Docker Stack Management

Manage the HomePilot Agent Docker Compose stack (n8n, Zabbix, LLM, SearXNG, Radicale, Whisper, Piper).

## When to Use

- Starting/stopping/restarting the stack or individual services
- Checking container health or logs
- Managing Docker secrets
- Deploying monitoring overlay (Zabbix)
- Configuring GPU assignment for LLM services
- Troubleshooting container networking

## Stack Architecture

| Service | Profile | Purpose | Port |
|---------|---------|---------|------|
| n8n | default | Workflow engine, AI agent | 5678 |
| zabbix-server | monitoring | Monitoring server | 10051 |
| zabbix-web | monitoring | Zabbix UI | 8084 |
| zabbix-postgres | monitoring | Zabbix DB | 5432 |
| llm | gpu | Qwen3-14B inference | 8081 |
| llm-embed | gpu | BGE-M3 embeddings | 8082 |
| searxng | default | Meta-search engine | 8888 |
| radicale | default | CalDAV calendar | 5232 |
| whisper | voice | Speech-to-text | 9000 |
| piper | voice | Text-to-speech | 5000 |

## Commands

### Start/Stop
```bash
# Full stack (no GPU)
docker compose up -d

# With GPU
docker compose --profile gpu up -d

# With GPU + voice
docker compose --profile gpu --profile voice up -d

# With monitoring overlay
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Stop everything
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down

# Restart single service
docker compose restart n8n
docker compose --profile gpu restart llm
```

### Health Checks
```bash
# All service status
docker compose ps

# n8n health
curl -s http://localhost:5678/healthz

# Zabbix API
curl -s http://localhost:8084/api_jsonrpc.php -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"apiinfo.version","id":1}'

# LLM inference
curl -s http://localhost:8081/v1/models | jq '.data[].id'

# Embedding service
curl -s http://localhost:8082/v1/models | jq '.data[].id'
```

### Logs
```bash
# Service logs
docker compose logs n8n --tail 100 -f
docker compose logs zabbix-server --tail 50

# GPU service logs
docker compose --profile gpu logs llm --tail 50
```

### Docker Secrets
```bash
# Setup credentials (generates secret files)
./scripts/setup-credentials.sh

# List secrets
docker compose config | grep -A2 secrets

# Secret files location
ls -la secrets/
ls -la monitoring/zabbix/secrets/
```

### GPU Management
```bash
# Check GPU availability
nvidia-smi

# Verify GPU assignment (RTX 4000 Ada SFF)
# GPU 0: Qwen3-14B (llm service) — ~15GB VRAM
# GPU 1: BGE-M3 (llm-embed service)
docker compose --profile gpu exec llm nvidia-smi
docker compose --profile gpu exec llm-embed nvidia-smi
```

## File Structure
```
homepilot-agent/
├── docker-compose.yml              # Main stack
├── docker-compose.monitoring.yml   # Zabbix overlay
├── docker/n8n/Dockerfile           # Custom n8n image
├── docker/n8n/entrypoint.sh        # Reads Docker secrets -> env vars
├── docker/searxng/Dockerfile       # Custom SearXNG
├── docker/piper/Dockerfile         # Custom Piper TTS
├── secrets/                        # Docker secret files (gitignored)
├── monitoring/zabbix/
│   ├── alertscripts/               # Matrix webhook scripts
│   │   ├── matrix_webhook.sh       # Bash (container-compatible)
│   │   └── matrix_webhook.py       # Python fallback
│   └── secrets/                    # Zabbix Docker secrets (gitignored)
├── models/                         # LLM model files (gitignored)
├── n8n/workflows/                  # JSON workflow definitions
└── scripts/
    ├── download-model.sh            # Download Qwen3-14B-Q8_0.gguf
    ├── download-whisper-model.sh   # Download Whisper model
    ├── import-workflows.sh         # Import n8n workflows via API
    ├── init-zabbix.sh              # Initialize Zabbix (hosts, templates, media)
    ├── install-zabbix-agent2.sh    # Install agent2 on VMs
    └── setup-credentials.sh        # Generate secret files
```

## Troubleshooting

- **n8n won't start**: Check `N8N_ENCRYPTION_KEY` in Docker secrets. If missing, run `./scripts/setup-credentials.sh`.
- **GPU OOM**: Reduce `LLAMA_ARG_CTX_SIZE` or switch to smaller model quantization.
- **Zabbix not receiving data**: Check agent2 connectivity with `zabbix_get -s 127.0.0.1 -k agent.ping`.
- **Docker networking**: Services communicate on `agent-net` (LLM) and `svc-net` (n8n+search+calendar). Use service names as hostnames.
- **Port conflicts**: Default ports can be overridden via `.env` file.