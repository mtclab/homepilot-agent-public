#!/usr/bin/env bash
set -e

cd /usr/src

.venv/bin/python3 -m wyoming_piper \
    --uri 'tcp://0.0.0.0:10200' \
    --data-dir /data \
    --voice "${PIPER_VOICE:-en_US-lessac-medium}" \
    --length-scale "${PIPER_LENGTH_SCALE:-1.0}" \
    --noise-scale "${PIPER_NOISE_SCALE:-0.667}" \
    --noise-w "${PIPER_NOISE_W:-0.333}" &

WYOMING_PID=$!

.venv/bin/python3 -m wyoming.http.tts_server \
    --uri 'tcp://localhost:10200' \
    --host '0.0.0.0' \
    --port 5000 &

HTTP_PID=$!

wait -n