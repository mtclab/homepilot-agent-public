---
name: voice-pipeline
description: Manage voice pipeline for HomePilot Agent. Trigger on voice, whisper, piper, speech, STT, TTS, transcription, text-to-speech, audio. Covers Whisper STT service, Piper TTS service, voice webhook, and n8n voice assistant workflow.
---

# Voice Pipeline

Manage the voice input/output pipeline (Whisper STT + Piper TTS) for HomePilot Agent.

## When to Use

- Starting or debugging Whisper (speech-to-text) or Piper (text-to-speech)
- Configuring the voice assistant n8n workflow
- Testing voice transcription or synthesis
- Troubleshooting voice webhook endpoints
- Switching voice profiles or models

## Architecture

```
Voice input (Telegram/web)
  → Whisper STT (port 9000) — transcribes audio to text
  → n8n AI Agent node — processes text with LLM + MCP tools
  → Piper TTS (port 5000) — synthesizes response to audio
  → Voice output back to user
```

## Commands

### Start/Stop
```bash
# Start voice services
docker compose --profile voice up -d whisper piper

# Check health
curl -s http://localhost:9000/health 2>/dev/null || echo "Whisper not responding"
curl -s http://localhost:5000/health 2>/dev/null || echo "Piper not responding"
```

### Test Whisper STT
```bash
# Transcribe audio file
curl -s http://localhost:9000/asr \
  -F "audio_file=@recording.wav" \
  -F "language=en" | jq '.text'
```

### Test Piper TTS
```bash
# Synthesize speech
curl -s http://localhost:5000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "HomePilot is online and all systems are running normally.", "voice": "en_US-lessac-medium"}' \
  --output test_response.wav
```

### Download Models
```bash
# Whisper model
./scripts/download-whisper-model.sh

# Piper voices (bundled in Docker image)
# Custom voices: https://github.com/rhasspy/piper/blob/master/VOICES.md
```

## Configuration

### Environment Variables
```env
WHISPER_URL=http://whisper:9000
PIPER_URL=http://piper:5000
VOICE_WEBHOOK_SECRET=<shared-secret>
PIPER_VOICE=en_US-lessac-medium    # Default voice
WHISPER_MODEL=base                  # tiny/base/small/medium/large
```

### n8n Voice Workflow
The `voice-assistant.json` workflow handles:
1. Receives audio via webhook (`/webhook/voice`)
2. Forwards to Whisper for transcription
3. Sends transcript to n8n AI Agent (Qwen3-14B + MCP tools)
4. Sends response text to Piper for synthesis
5. Returns audio to user

## Troubleshooting

- **Whisper not loading model**: Ensure `models/whisper-base.pt` exists, check `WHISPER_MODEL` env var
- **Piper no audio output**: Verify correct voice name, check Docker logs for missing voice data
- **Voice webhook 401**: Check `VOICE_WEBHOOK_SECRET` matches between n8n and caller
- **Latency too high**: Switch Whisper to `tiny` model, use smaller Piper voice
- **GPU not available for Whisper**: Whisper uses CPU by default (compose profile `voice`), no GPU needed