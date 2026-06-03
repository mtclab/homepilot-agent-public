# n8n Integration Architecture

## Ownership

**n8n owns all user-facing notifications and the conversational interface.** HomePilot does not embed a notification daemon, persona, or Matrix bot. The opencode orchestra does not send user-facing messages (Matrix room is agent telemetry only).

## Artifact-proposed event flow

```
lifecycle.propose()                   (HomePilot)
  → POST to HP_EVENTS_WEBHOOK_URL     (outgoing webhook hook)
  → n8n Webhook trigger node          (artifact-notification workflow)
  → format message                    (intent, kind, host, review link)
  → POST to Matrix room               (matrix-bot credentials)
  → (optional) Telegram DM            (configurable, off by default)
```

Payload schema defined in mtclab/homepilot-v2#147. Fields used by notification workflow:

```json
{
  "event": "artifact_proposed",
  "artifact": {
    "id": "uuid",
    "intent": "...",
    "kind": "...",
    "host": "...",
    "proposed_at": "ISO8601"
  }
}
```

## Token hygiene

Two token scopes exist in HomePilot (mtclab/homepilot-v2#149):

| Token env var | Scope | Used by |
|---------------|-------|---------|
| `HP_MCP_TOKEN` | Read-only | Chat assistant, morning briefing, inventory queries |
| `HP_MCP_TOKEN_RW` | Read-write (includes `propose_artifact`, `record_fact`) | Personal assistant AI Agent |

n8n workflows use the read-only token by default. The AI Agent core workflow uses read-write only for explicit mutation requests (`propose_artifact`, `record_fact`).

`propose_artifact` does **not** apply changes — it creates a pending artifact requiring human approval in the HomePilot web UI.

## Workflow storage

n8n workflow definitions live in n8n's own database (not this repo). JSON exports are version-controlled under `n8n/workflows/` for reproducible deploys. Import with `scripts/import-workflows.sh` on a fresh instance.

## Environment variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `HP_EVENTS_WEBHOOK_URL` | HomePilot config | Where HomePilot POSTs artifact events. Set to `http://<n8n-host>:5678/webhook/<path>` |
| `HP_MCP_URL` | n8n workflows | HomePilot MCP HTTP endpoint, e.g. `http://<proxmox-lxc>:8000/mcp` |
| `HP_MCP_TOKEN` | n8n workflows | Read-only MCP bearer token |
| `HP_MCP_TOKEN_RW` | n8n AI Agent | Read-write MCP bearer token (propose + record only) |
| `LLM_BASE_URL` | n8n workflows + "LLM API" credential | Base URL of the external OpenAI-compatible endpoint (must end in `/v1`), e.g. `http://<ollama-host>:11434/v1` |
| `LLM_MODEL` | n8n workflows | Model name/tag served by the endpoint, e.g. `qwen3:14b` |
| `LLM_API_KEY` | "LLM API" credential | API key for the endpoint; any non-empty placeholder for keyless local servers |

## Internal service endpoints

| Service | Internal hostname | Port | Purpose |
|---------|------------------|------|---------|
| llm | external — `LLM_BASE_URL` | — | OpenAI-compatible chat API (any provider; set in n8n "LLM API" credential) |
| searxng | `http://searxng:8888` | 8888 | Web search JSON API |
| radicale | `http://radicale:5232` | 5232 | CalDAV calendar |
| n8n | `http://n8n:5678` | 5678 | Workflow engine + webhook receiver |
