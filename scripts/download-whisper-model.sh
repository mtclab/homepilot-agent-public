#!/usr/bin/env bash
set -euo pipefail

# Downloads faster-whisper model for the whisper sidecar container.
# Run before first docker compose up if using voice features.
# Idempotent: skips if model already exists in cache directory.

MODEL_SIZE="${WHISPER_MODEL:-base}"
CACHE_DIR="$(cd "$(dirname "$0")/.." && pwd)/models/whisper"

mkdir -p "${CACHE_DIR}"

REPO="Systran/faster-whisper-${MODEL_SIZE}"
FILE_URL="https://huggingface.co/${REPO}/resolve/main/model.bin"
DEST="${CACHE_DIR}/${MODEL_SIZE}/model.bin"

if [[ -f "${DEST}" ]]; then
    echo "Model already cached: ${DEST}"
    echo "To re-download, delete this file and re-run."
    exit 0
fi

echo "Downloading faster-whisper ${MODEL_SIZE} model from HuggingFace..."
echo "  Repo: ${REPO}"
echo "  Dest: ${DEST}"
echo ""

if command -v wget &>/dev/null; then
    wget --continue --show-progress -O "${DEST}" "${FILE_URL}"
elif command -v curl &>/dev/null; then
    curl -L --continue-at - --progress-bar -o "${DEST}" "${FILE_URL}"
else
    echo "ERROR: wget or curl required for download." >&2
    exit 1
fi

echo ""
echo "Download complete: ${DEST}"
echo ""
echo "NOTE: The faster-whisper-server container auto-downloads the model on first"
echo "startup. This script is for pre-seeding the cache. To use the auto-download"
echo "instead, just start the whisper service and wait for 'Model loaded' in logs:"
echo "  docker compose --profile voice up whisper -d"
echo "  docker compose logs -f whisper"
echo ""
echo "Supported model sizes: tiny, base, small, medium, large-v2, large-v3"
echo "Current: ${MODEL_SIZE}"
echo "Change via WHISPER_MODEL env var: WHISPER_MODEL=small $0"