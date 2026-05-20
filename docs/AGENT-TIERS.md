# Agent Tiers

Defines what each AI system in the homelab owns. Prevents two systems claiming the same action.

## Tier table

| System | Role | Can mutate HomePilot? | Owns notifications? | Memory |
|--------|------|-----------------------|---------------------|--------|
| **HomePilot** | IaC engine — tracks drift, proposes artifacts, applies approved changes | Yes (propose → approve → apply cycle) | No | Artifact store + KB |
| **opencode orchestra** | Ephemeral dev-task agents | Via PR only | No (Matrix room = agent telemetry) | Per-task handoffs in context |
| **n8n** | Event routing + workflow automation + **personal agent (AI Agent node)** | Read-only via MCP | **Yes** (all user-facing notifications + chat) | Stateless — homelab facts via HomePilot KB (`search_kb` / `record_fact`) |
| ~~Personal agent service~~ | *Replaced by n8n AI Agent node* | — | — | — |

## Key decisions

**n8n AI Agent node is the personal agent.** No separate Python service. n8n already running; AI Agent node covers the conversational loop without a new deployment target.

**n8n owns all user-facing notifications.** HomePilot emits events via webhook; n8n routes them to Matrix / Telegram. HomePilot does not embed a notification daemon or persona.

**HomePilot KB is the memory layer.** n8n workflows call `search_kb` and `record_fact` via MCP for persistent homelab facts. n8n itself is stateless between executions.

**Mutations require human approval.** n8n may call `propose_artifact` (via read-write token, used sparingly). The artifact sits in HomePilot's review queue; no change applies without an explicit `approve` action in the HomePilot web UI.

## MCP tool assignments

| Tool | Who calls it | Token scope |
|------|-------------|-------------|
| `query_inventory` | n8n AI Agent, morning briefing | read-only |
| `get_environment_doc` | n8n AI Agent, chat assistant | read-only |
| `search_kb` | n8n AI Agent | read-only |
| `record_fact` | n8n AI Agent | read-write |
| `propose_artifact` | n8n AI Agent (on explicit user request) | read-write |
| `query_artifacts` | n8n AI Agent, morning briefing | read-only |

## Graduation path

If persistent cross-session memory or complex multi-turn state becomes a real need, graduate n8n AI Agent to a thin Python service. That service would own the same MCP surface — the token model and notification ownership do not change.
