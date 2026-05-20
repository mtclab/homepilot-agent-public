#!/usr/bin/env bash
set -euo pipefail

# Downloads Qwen3-14B Q8_0 GGUF from HuggingFace into ./models/
# Run before first docker compose up.
# Idempotent: skips download if file already exists and SHA256 matches.

REPO="unsloth/Qwen3-14B-GGUF"
FILENAME="Qwen3-14B-Q8_0.gguf"
MODELS_DIR="$(cd "$(dirname "$0")/.." && pwd)/models"
DEST="${MODELS_DIR}/${FILENAME}"

# SHA256 from HuggingFace model card — update if the file changes upstream
EXPECTED_SHA256="VERIFY_FROM_HF_MODEL_CARD"

# Determine download URL
HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
FILE_URL="${HF_ENDPOINT}/${REPO}/resolve/main/${FILENAME}"

mkdir -p "${MODELS_DIR}"

check_sha256() {
    local file="$1"
    if [[ "${EXPECTED_SHA256}" == "VERIFY_FROM_HF_MODEL_CARD" ]]; then
        echo "WARNING: EXPECTED_SHA256 not set — skipping checksum verification." >&2
        echo "  Update EXPECTED_SHA256 in this script after verifying from HuggingFace." >&2
        return 0
    fi
    echo "Verifying SHA256..."
    local actual
    actual=$(sha256sum "${file}" | awk '{print $1}')
    if [[ "${actual}" != "${EXPECTED_SHA256}" ]]; then
        echo "ERROR: SHA256 mismatch!" >&2
        echo "  expected: ${EXPECTED_SHA256}" >&2
        echo "  actual:   ${actual}" >&2
        rm -f "${file}"
        return 1
    fi
    echo "SHA256 verified."
}

if [[ -f "${DEST}" ]]; then
    echo "File already exists: ${DEST}"
    check_sha256 "${DEST}"
    echo "Model ready. No download needed."
    exit 0
fi

echo "Downloading ${FILENAME} (~37 GB) from ${FILE_URL}"
echo "This will take a while. Download resumes if interrupted."

# Use wget with resume support if available, fall back to curl
if command -v wget &>/dev/null; then
    wget --continue --show-progress -O "${DEST}" "${FILE_URL}"
elif command -v huggingface-cli &>/dev/null; then
    huggingface-cli download "${REPO}" "${FILENAME}" --local-dir "${MODELS_DIR}"
else
    curl -L --continue-at - --progress-bar -o "${DEST}" "${FILE_URL}"
fi

check_sha256 "${DEST}"
echo "Download complete: ${DEST}"
