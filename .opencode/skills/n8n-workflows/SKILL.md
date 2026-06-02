---
name: n8n-workflows
description: Manage n8n workflow automation for HomePilot Agent. Trigger on n8n, workflow, personal assistant, chat assistant, morning briefing, artifact notification, calendar trigger, voice assistant, webhook, MCP tool, AI agent. Covers importing workflows, configuring MCP connections, webhook setup, and workflow debugging.
---

# n8n Workflows

Manage n8n workflow automation — the personal AI agent layer of HomePilot.

## When to Use

- Importing or updating n8n workflows
- Configuring MCP connections from n8n to HomePilot
- Setting up webhook endpoints for HomePilot event notifications
- Debugging workflow execution failures
- Configuring Telegram or Matrix bot integrations
- Working with the AI Agent node (Qwen3-14B + MCP tools)

## Workflows

| Workflow | File | Purpose |
|----------|------|---------|
| Personal Assistant | `n8n/workflows/personal-assistant.json` | Telegram → Qwen3-14B + all MCP tools → reply |
| Chat Assistant | `n8n/workflows/chat-assistant.json` | Read-only Telegram bot via HomePilot MCP |
| Artifact Notification | `n8n/workflows/artifact-notification.json` | Webhook from HomePilot → format → Matrix + Telegram |
| Morning Briefing | `n8n/workflows/morning-briefing.json` | Daily 08:00 drift + artifact summary |
| Calendar Trigger | `n8n/workflows/calendar-trigger.json` | Radicale `hp:propose` events → HomePilot |
| Voice Assistant | `n8n/workflows/voice-assistant.json` | Voice webhook → Whisper STT → LLM → Piper TTS |

## MCP Integration

n8n connects to HomePilot via MCP over HTTP:

```bash
# MCP URL (in n8n environment)
HP_MCP_URL=http://your-server.local:8000/mcp

# Read-only token (queries, search_kb, query_inventory)
HP_MCP_TOKEN=hp_xxx_read_only_token

# Read-write token (propose_artifact, record_fact)
HP_MCP_TOKEN_RW=hp_xxx_read_write_token
```

### MCP Tool Mapping

| Tool | Token Scope | Who calls it |
|------|-------------|-------------|
| `query_inventory` | read-only | AI Agent, morning briefing |
| `get_environment_doc` | read-only | AI Agent, chat assistant |
| `search_kb` | read-only | AI Agent |
| `record_fact` | read-write | AI Agent |
| `propose_artifact` | read-write | AI Agent (explicit user request only) |
| `query_artifacts` | read-only | AI Agent, morning briefing |

## Import Workflows

```bash
# Import all workflows
./scripts/import-workflows.sh

# Import single workflow via API
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @n8n/workflows/personal-assistant.json

# List active workflows
curl -s http://localhost:5678/api/v1/workflows | jq '.data[].name'
```

## Webhook Setup

HomePilot sends artifact events to n8n via webhook:

```
POST http://<n8n-host>:5678/webhook/artifact-proposed
Header: X-HP-Webhook-Secret: <shared_secret>
Body: { "event": "artifact.proposed", "artifact_id": 123, ... }
```

## Troubleshooting

- **Workflow not triggering**: Check n8n is active, webhook path matches, `X-HP-Webhook-Secret` header matches
- **MCP connection failed**: Verify `HP_MCP_URL` and `HP_MCP_TOKEN` in n8n environment
- **AI Agent node not responding**: Check LLM service is running (`curl http://localhost:8081/v1/models`)
- **Telegram bot not working**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID` in secrets