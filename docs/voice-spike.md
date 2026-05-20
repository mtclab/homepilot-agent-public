# Voice Spike — Whisper + Piper via LocalAI

End-to-end voice: speech-in via Whisper, route through n8n AI Agent, speech-out via Piper TTS.

## Hardware

- GPU: RTX 4000 Ada SFF (20GB VRAM) × 3
- Ollama and LocalAI already running on homelab

## Architecture

```
Microphone
  → whisper.cpp / LocalAI Whisper endpoint
  → transcription (text)
  → n8n AI Agent node (Qwen3-14B via llama.cpp)
  → HomePilot MCP tools (if homelab question)
  → reply text
  → Piper TTS / LocalAI TTS endpoint
  → audio output
```

## Step 1 — Check existing LocalAI endpoints

Before adding new services, verify Whisper and Piper are already served:

```bash
# Check LocalAI model list
curl -s http://<localai-host>:8080/models | jq '.data[].id'

# Test Whisper transcription
curl -s -X POST http://<localai-host>:8080/v1/audio/transcriptions \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.wav" \
  -F "model=whisper-1" | jq .

# Test Piper TTS
curl -s -X POST http://<localai-host>:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "en-us-piper", "input": "Hello homelab", "voice": "alloy"}' \
  -o reply.wav && aplay reply.wav
```

## Step 2 — Whisper model selection

| Model | VRAM | WER (homelab terms) | Latency |
|-------|------|---------------------|---------|
| whisper-base | ~200MB | ~12% on domain terms | ~0.3s |
| whisper-small | ~500MB | ~8% | ~0.6s |
| whisper-medium | ~1.5GB | ~5% | ~1.2s |
| whisper-large-v3 | ~3GB | ~3% | ~2.5s |

Recommended: **whisper-medium** for domain accuracy on terms like Proxmox, Authentik, artifact, drift. Falls within 5s round-trip target.

## Step 3 — TTS model selection

Piper voices for en-US: `en_US-lessac-medium`, `en_US-ryan-high` (higher quality, slower).

Test domain term pronunciation:
```bash
echo "Proxmox artifact proposed for nginx update" | piper --model en_US-ryan-high --output_file test.wav
aplay test.wav
```

## Step 4 — n8n voice workflow

Wire into n8n AI Agent:

1. HTTP Trigger receives audio (base64 or multipart)
2. HTTP Request node → LocalAI Whisper transcription
3. AI Agent node (same as personal-assistant workflow)
4. HTTP Request node → LocalAI Piper TTS → audio bytes
5. Return audio (or save to file + return URL)

For Telegram voice messages: Telegram sends `voice.file_id` → download via Bot API → send to Whisper.

## Latency budget (target: under 5s)

| Step | Expected | Measured |
|------|----------|----------|
| Whisper transcription (medium, ~5s audio) | 0.8–1.2s | _fill in_ |
| n8n routing overhead | ~0.1s | _fill in_ |
| LLM inference (Qwen3-14B, ~100 token reply) | 0.8–1.5s | _fill in_ |
| Piper TTS (~100 words) | 0.3–0.5s | _fill in_ |
| **Total** | **2.7–4.3s** | _fill in_ |

## Domain accuracy test cases

Transcribe these sentences and verify correctness:
- "Is there any drift on the Proxmox nodes?"
- "Propose an artifact to update the Authentik container"
- "Search the KB for the nginx configuration"
- "What artifacts are pending review?"

Record results in the Measured column above.

## Notes

- If Whisper and Piper are not available via LocalAI, add them to `docker-compose.yml` as a `localai` service
- whisper.cpp can run directly on CPU — VRAM not required for transcription if GPUs are saturated
- Piper is CPU-only TTS — no GPU contention with LLM
