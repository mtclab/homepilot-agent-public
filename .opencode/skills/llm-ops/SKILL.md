---
name: llm-ops
description: Manage local LLM inference services for HomePilot Agent. Trigger on LLM, Qwen, llama.cpp, inference, embedding, model download, GPU, VRAM, context size, generation. Covers model download, GPU assignment, context configuration, and inference service management.
---

# LLM Operations

Manage local LLM inference services (Qwen3-14B + BGE-M3 embeddings) for HomePilot Agent.

## When to Use

- Downloading or switching LLM models
- Configuring context size, parallel requests, or GPU assignment
- Monitoring GPU memory usage
- Debugging inference failures
- Switching between GPU and CPU inference
- Configuring embedding service for HomePilot KB

## Architecture

| Service | Profile | Model | GPU | Port |
|---------|---------|-------|-----|------|
| llm | gpu | Qwen3-14B-Q8_0 (~15GB) | GPU 0 (RTX 4000 Ada) | 8081 |
| llm-embed | gpu | BGE-M3 (~2GB) | GPU 1 (RTX 4000 Ada) | 8082 |

Both use llama.cpp server with OpenAI-compatible API.

## Commands

### Download Models
```bash
# Download Qwen3-14B-Q8_0 (default)
./scripts/download-model.sh

# Download Whisper model
./scripts/download-whisper-model.sh

# Models stored in ./models/ (gitignored)
ls -lh models/
```

### Start/Stop
```bash
# Start with GPU
docker compose --profile gpu up -d llm llm-embed

# Check inference health
curl -s http://localhost:8081/v1/models | jq '.data[].id'
curl -s http://localhost:8082/v1/models | jq '.data[].id'

# Stop GPU services
docker compose --profile gpu down llm llm-embed
```

### Test Inference
```bash
# Chat completion
curl -s http://localhost:8081/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-14B-Q8_0",
    "messages": [{"role": "user", "content": "Hello, what is HomePilot?"}],
    "max_tokens": 200
  }' | jq '.choices[0].message.content'

# Embedding
curl -s http://localhost:8082/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "BGE-M3",
    "input": "Search the knowledge base for Proxmox configuration"
  }' | jq '.data[0].embedding[:5]'
```

### GPU Monitoring
```bash
# GPU status
nvidia-smi

# Per-container GPU usage
docker compose --profile gpu exec llm nvidia-smi
docker compose --profile gpu exec llm-embed nvidia-smi

# VRAM usage (Qwen3-14B-Q8_0 uses ~15GB)
watch -n 5 nvidia-smi
```

## Configuration

### Environment Variables
```env
# LLM service
GGUF_MODEL_FILENAME=Qwen3-14B-Q8_0.gguf
LLAMA_ARG_CTX_SIZE=8192      # Context window size
LLAMA_ARG_PARALLEL=4          # Parallel request slots

# Embedding service
EMBED_MODEL_FILENAME=bge-m3.gguf
```

### Model Files
```bash
models/
├── Qwen3-14B-Q8_0.gguf   # Main LLM (~15GB)
├── bge-m3.gguf           # Embedding model (~2GB)
└── whisper-base.pt        # Whisper STT model
```

## Troubleshooting

- **GPU OOM**: Reduce `LLAMA_ARG_CTX_SIZE` or switch to Q5_K_M quantization (~10GB)
- **Model not found**: Run `./scripts/download-model.sh`, check `models/` directory
- **Slow inference**: Check GPU utilization with `nvidia-smi`, reduce `LLAMA_ARG_PARALLEL`
- **Embedding service down**: Check BGE-M3 model is in `models/`, verify GPU 1 is available
- **n8n can't reach LLM**: Check `agent-net` Docker network, verify `LLM_URL=http://llm:8081` in n8n env