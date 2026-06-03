#!/usr/bin/env python3
"""Matrix → n8n webhook bridge. Polls Matrix /sync and forwards messages to n8n."""

import json
import os
import sys
import time
import logging
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("matrix-bridge")

MATRIX_SERVER = os.environ.get("MATRIX_SERVER", "https://matrix.example.com")
def _load_token() -> str:
    token_file = os.environ.get("MATRIX_ACCESS_TOKEN_FILE", "")
    if token_file:
        for attempt in range(3):
            try:
                return Path(token_file).read_text().strip()
            except PermissionError:
                import subprocess
                try:
                    result = subprocess.run(["cat", token_file], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip()
                except Exception:
                    pass
            time.sleep(1)
    return os.environ.get("MATRIX_ACCESS_TOKEN", "")

MATRIX_ACCESS_TOKEN = _load_token()
MATRIX_ROOM_ID = os.environ.get(
    "MATRIX_ROOM_ID",
    ":your-room-id:example.com",
)
MATRIX_BOT_USER = os.environ.get("MATRIX_BOT_USER", "bot-username")
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL", "http://n8n:5678/webhook/matrix-incoming"
)
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "30000"))
SYNC_DELAY = int(os.environ.get("SYNC_DELAY", "2"))

FILTER_ID = None


def create_filter() -> str:
    """Create a Matrix filter to only get message events in our room."""
    global FILTER_ID
    filter_def = {
        "room": {
            "rooms": [MATRIX_ROOM_ID],
            "ephemeral": {"not_types": ["*"]},
            "state": {"not_types": ["*"]},
            "account_data": {"not_types": ["*"]},
        },
        "presence": {"not_types": ["*"]},
    }
    try:
        r = requests.put(
            f"{MATRIX_SERVER}/_matrix/client/v3/user/{MATRIX_BOT_USER}/filter",
            headers={"Authorization": f"Bearer {MATRIX_ACCESS_TOKEN}"},
            json=filter_def,
            timeout=10,
        )
        r.raise_for_status()
        FILTER_ID = r.json().get("filter_id")
        log.info(f"Created filter: {FILTER_ID}")
    except Exception as e:
        log.warning(f"Failed to create filter, polling without: {e}")


def sync(since: str | None = None) -> dict:
    """Long-poll Matrix /sync."""
    params = {
        "timeout": POLL_TIMEOUT,
        "access_token": MATRIX_ACCESS_TOKEN,
    }
    if since:
        params["since"] = since
    if FILTER_ID:
        params["filter"] = FILTER_ID
    r = requests.get(
        f"{MATRIX_SERVER}/_matrix/client/v3/sync",
        params=params,
        timeout=(POLL_TIMEOUT // 1000) + 30,
    )
    r.raise_for_status()
    return r.json()


def forward_to_n8n(event: dict) -> bool:
    """POST message event to n8n webhook."""
    content = event.get("content", {})
    text = content.get("body", content.get("formatted_body", ""))
    if not text:
        return False
    payload = {
        "sender": event.get("sender", ""),
        "room_id": event.get("room_id", MATRIX_ROOM_ID),
        "event_id": event.get("event_id", ""),
        "content": content,
        "type": event.get("type", ""),
        "origin_server_ts": event.get("origin_server_ts", 0),
    }
    try:
        r = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )
        log.info(f"Forwarded event {payload['event_id'][:16]}… status={r.status_code}")
        return r.status_code < 300
    except Exception as e:
        log.error(f"Failed to forward to n8n: {e}")
        return False


def main():
    if not MATRIX_ACCESS_TOKEN:
        log.error("MATRIX_ACCESS_TOKEN not set")
        sys.exit(1)

    create_filter()
    since = None
    log.info(f"Bridge started — room={MATRIX_ROOM_ID}, webhook={N8N_WEBHOOK_URL}")

    while True:
        try:
            data = sync(since)
            since = data.get("next_batch", since)

            rooms = data.get("rooms", {}).get("join", {})
            room_events = rooms.get(MATRIX_ROOM_ID, {}).get("timeline", {}).get("events", [])

            for event in room_events:
                etype = event.get("type", "")
                if etype != "m.room.message":
                    continue
                sender = event.get("sender", "")
                if sender == MATRIX_BOT_USER:
                    continue
                content = event.get("content", {})
                msgtype = content.get("msgtype", "")
                if msgtype not in ("m.text", "m.notice", "m.emote"):
                    continue
                log.info(f"Message from {sender}: {content.get('body', '')[:60]}")
                forward_to_n8n(event)

        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.ConnectionError as e:
            log.error(f"Connection error: {e}")
            time.sleep(5)
        except Exception as e:
            log.error(f"Sync error: {e}")
            time.sleep(SYNC_DELAY)


if __name__ == "__main__":
    main()