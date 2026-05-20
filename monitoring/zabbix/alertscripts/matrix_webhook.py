#!/usr/bin/env python3
"""Zabbix → Matrix webhook alert script.

Called by Zabbix webhook media type. Sends alert notifications to a Matrix room.

Environment variables:
  MATRIX_SERVER  — Matrix homeserver URL (e.g. https://matrix.example.com)
  MATRIX_ROOM_ID — Target room ID (e.g. !xxxxx:example.com)
  MATRIX_TOKEN   — Bot access token

Zabbix passes these parameters:
  ALERT_SUBJECT  — Trigger name
  ALERT_MESSAGE  — Full alert message
  ALERT_SENDTO    — Not used (room is configured per media type)
  ZABBIX_URL     — Link to the event in Zabbix UI (optional)
"""

import json
import os
import sys
import urllib.request
import urllib.error


def send_matrix_notification(subject: str, message: str, zabbix_url: str = "") -> None:
    server = os.environ.get("MATRIX_SERVER", "").rstrip("/")
    room_id = os.environ.get("MATRIX_ROOM_ID", "")
    token = os.environ.get("MATRIX_TOKEN", "")

    if not all([server, room_id, token]):
        print(f"ERROR: Missing environment variables. MATRIX_SERVER={server}, ROOM_ID={'set' if room_id else 'missing'}, TOKEN={'set' if token else 'missing'}")
        sys.exit(1)

    severity = "UNKNOWN"
    for line in message.split("\n"):
        if "Problem" in line or "severity" in line.lower():
            for level in ["Disaster", "High", "Average", "Warning", "Information"]:
                if level in line:
                    severity = level.upper()
                    break
            break

    icon = {"DISASTER": "🔴", "HIGH": "🟠", "AVERAGE": "🟡", "WARNING": "🟡", "INFORMATION": "🔵"}.get(severity, "⚪")

    body = f"{icon} **[{severity}] {subject}**\n\n{message}"
    if zabbix_url:
        body += f"\n\n[View in Zabbix]({zabbix_url})"

    url = f"{server}/_matrix/client/v3/rooms/{room_id}/send/m.room.message"
    payload = {
        "msgtype": "m.text",
        "body": body,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="PUT",
    )

    # Add transaction ID to prevent duplicates
    import uuid
    req.full_url = f"{url}/{uuid.uuid4().hex}"

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Matrix notification sent: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"ERROR: Matrix API returned {e.code}: {e.read().decode()}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Network error: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    subject = os.environ.get("ZABBIX_ALERT_SUBJECT", os.environ.get("ALERT_SUBJECT", "Zabbix Alert"))
    message = os.environ.get("ZABBIX_ALERT_MESSAGE", os.environ.get("ALERT_MESSAGE", ""))
    zabbix_url = os.environ.get("ZABBIX_URL", "")
    send_matrix_notification(subject, message, zabbix_url)