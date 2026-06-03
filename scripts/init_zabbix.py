#!/usr/bin/env python3
"""Initialize Zabbix monitoring stack.

Called by init-zabbix.sh after .env.monitoring is loaded.
All Zabbix API interactions happen here.

Usage: python3 init_zabbix.py [--url URL] [--user USER] [--password PASS]
                                [--new-password PASS] [--pve-url URL]
                                [--pve-token-id ID] [--pve-token-secret SECRET]
                                [--matrix-server URL] [--matrix-room-id ID]
                                [--matrix-token TOKEN]
                                [--agent-hostname NAME] [--agent-ip IP]

Or via environment variables (loaded by the bash wrapper from .env.monitoring).
"""

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse


class ZabbixAPI:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.token: str | None = None

    def login(self) -> str:
        result = self._call("user.login", {"username": self.user, "password": self.password})
        self.token = result
        return self.token

    def logout(self):
        if self.token:
            self._call("user.logout", [], auth=self.token)

    def _call(self, method: str, params, auth=None):
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        if auth:
            payload["auth"] = auth
        data = json.dumps(payload).encode()
        req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            print(f"  HTTP error: {e.code} {e.read().decode()[:200]}")
            return None
        if "error" in result:
            print(f"  API error: {result['error']}")
            return None
        return result.get("result")

    def api(self, method: str, params):
        return self._call(method, params, auth=self.token)


def wait_for_ui(url: str, timeout: int = 300):
    print("Waiting for Zabbix web UI...")
    for i in range(timeout // 10):
        try:
            req = urllib.request.Request(f"{url.rstrip('/')}/")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"  Zabbix UI ready after {(i+1)*10}s")
                    return True
        except Exception:
            pass
        time.sleep(10)
    print(f"  ERROR: Zabbix UI not ready after {timeout}s")
    return False


def change_password(api: ZabbixAPI, new_password: str):
    print("Changing admin password...")
    result = api.api("user.update", {"userid": "1", "current_passwd": api.password, "passwd": new_password})
    if result:
        print("  Password changed.")
        api.password = new_password
    else:
        print("  WARNING: Password change failed. Already changed?")


def create_proxmox_host(api: ZabbixAPI, pve_url: str, pve_token_id: str, pve_token_secret: str, hypervisors_gid: str):
    print("Setting up Proxmox host...")

    template_id = _get_template_id(api, "Proxmox VE by HTTP")
    if not template_id:
        print("  Proxmox VE by HTTP template not found. Skipping.")
        return

    parsed = urlparse(pve_url)
    pve_host = parsed.hostname or pve_url
    pve_port = str(parsed.port or (443 if parsed.scheme == "https" else 80))

    existing = api.api("host.get", {"filter": {"host": ["proxmox-ve"]}, "output": ["hostid"]})
    if existing:
        host_id = existing[0]["hostid"]
        print(f"  Proxmox host already exists (id={host_id}). Updating macros...")
        macros = api.api("usermacro.get", {"hostids": [host_id], "output": ["hostmacroid", "macro", "value"]})
        macro_map = {m["macro"]: m["hostmacroid"] for m in (macros or [])}
        updates = {
            "{$PVE.URL.HOST}": pve_host,
            "{$PVE.URL.PORT}": pve_port,
            "{$PVE.TOKEN.ID}": pve_token_id,
            "{$PVE.TOKEN.SECRET}": pve_token_secret,
        }
        for macro_name, value in updates.items():
            if macro_name in macro_map:
                api.api("usermacro.update", {"hostmacroid": macro_map[macro_name], "value": value})
            else:
                api.api("usermacro.create", {"hostid": host_id, "macro": macro_name, "value": value})
        print("  Macros updated.")
    else:
        macros = [
            {"macro": "{$PVE.URL.HOST}", "value": pve_host},
            {"macro": "{$PVE.URL.PORT}", "value": pve_port},
            {"macro": "{$PVE.TOKEN.ID}", "value": pve_token_id},
            {"macro": "{$PVE.TOKEN.SECRET}", "value": pve_token_secret},
        ]
        result = api.api("host.create", {
            "host": "proxmox-ve",
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": pve_host, "dns": "", "port": "10051"}],
            "groups": [{"groupid": hypervisors_gid}],
            "templates": [{"templateid": template_id}],
            "macros": macros,
        })
        if result:
            print(f"  Proxmox host created.")
        else:
            print("  Failed to create Proxmox host.")


def create_agent_host(api: ZabbixAPI, hostname: str, ip: str, linux_gid: str):
    print(f"Creating agent host ({hostname})...")

    linux_tid = _get_template_id(api, "Linux by Zabbix agent")
    docker_tid = _get_template_id(api, "Docker by Zabbix agent 2")
    templates = [{"templateid": linux_tid}] if linux_tid else []
    if docker_tid:
        templates.append({"templateid": docker_tid})

    if not templates:
        print("  No templates found. Skipping host creation.")
        return

    existing = api.api("host.get", {"filter": {"host": [hostname]}, "output": ["hostid"]})
    if existing:
        print(f"  Host {hostname} already exists (id={existing[0]['hostid']}).")
        return

    result = api.api("host.create", {
        "host": hostname,
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "10050"}],
        "groups": [{"groupid": linux_gid}],
        "templates": templates,
    })
    if result:
        print(f"  Agent host created.")
    else:
        print(f"  Failed to create agent host.")


def fix_zabbix_server_ip(api: ZabbixAPI, ip: str):
    print("Fixing Zabbix server host interface...")
    interfaces = api.api("hostinterface.get", {"filter": {"hostids": ["10084"]}, "output": ["interfaceid", "ip"]})
    if interfaces and interfaces[0]["ip"] != ip:
        api.api("hostinterface.update", {"interfaceid": interfaces[0]["interfaceid"], "ip": ip})
        print(f"  Updated to {ip}")
    else:
        print(f"  Already correct ({ip}).")


def create_matrix_media_type(api: ZabbixAPI, zabbix_url: str, matrix_server: str, matrix_room_id: str, matrix_token: str):
    print("Creating Matrix Webhook media type...")
    existing = api.api("mediatype.get", {"filter": {"name": ["Matrix Webhook"]}, "output": ["mediatypeid"]})
    if existing:
        mt_id = existing[0]["mediatypeid"]
        print(f"  Already exists (id={mt_id}). Updating parameters...")
        api.api("mediatype.update", {
            "mediatypeid": mt_id,
            "parameters": [
                {"sortorder": "0", "value": "{ALERT.SUBJECT}"},
                {"sortorder": "1", "value": "{ALERT.MESSAGE}"},
                {"sortorder": "2", "value": zabbix_url},
            ]
        })
        return mt_id

    result = api.api("mediatype.create", {
        "name": "Matrix Webhook",
        "type": "1",
        "exec_path": "matrix_webhook.sh",
        "parameters": [
            {"sortorder": "0", "value": "{ALERT.SUBJECT}"},
            {"sortorder": "1", "value": "{ALERT.MESSAGE}"},
            {"sortorder": "2", "value": zabbix_url},
        ]
    })
    if result:
        mt_id = result[0] if isinstance(result, list) else result.get("mediatypeids", [None])[0]
        print(f"  Created (id={mt_id}).")
        return mt_id
    return None


def add_admin_media(api: ZabbixAPI, mt_id: str):
    print("Adding Matrix media to Admin user...")
    api.api("user.update", {
        "userid": "1",
        "medias": [{"mediatypeid": mt_id, "sendto": "CHANGE_ME_matrix_room_alias", "active": "0", "severity": "63", "period": "1-7,00:00-24:00"}]
    })
    print("  Done.")


def create_trigger_action(api: ZabbixAPI, mt_id: str):
    print("Creating trigger action...")
    existing = api.api("action.get", {"filter": {"name": ["Send alerts to Matrix"]}, "output": ["actionid"]})
    if existing:
        print(f"  Already exists (id={existing[0]['actionid']}).")
        return

    result = api.api("action.create", {
        "name": "Send alerts to Matrix",
        "eventsource": "0",
        "status": "0",
        "operations": [{
            "operationtype": "0",
            "opmessage": {
                "mediatypeid": mt_id,
                "default_msg": "0",
                "message": "{EVENT.NAME}\nSeverity: {EVENT.SEVERITY}\nHost: {HOST.NAME}\nTime: {EVENT.DATE} {EVENT.TIME}\n\n{EVENT.OPDATA}",
            },
            "opmessage_usr": [{"userid": "1"}],
        }],
        "recovery_operations": [{
            "operationtype": "0",
            "opmessage": {
                "mediatypeid": mt_id,
                "default_msg": "0",
                "message": "RESOLVED: {EVENT.NAME}\nHost: {HOST.NAME}\nRecovery: {EVENT.RECOVERY.DATE} {EVENT.RECOVERY.TIME}",
            },
            "opmessage_usr": [{"userid": "1"}],
        }],
    })
    if result:
        print(f"  Action created (id={result.get('actionids', ['?'])[0]}).")
    else:
        print("  Failed to create action.")


def _get_template_id(api: ZabbixAPI, name: str) -> str | None:
    result = api.api("template.get", {"filter": {"host": [name]}, "output": ["templateid"]})
    if result:
        return result[0]["templateid"]
    return None


def _get_group_id(api: ZabbixAPI, name: str) -> str:
    result = api.api("hostgroup.get", {"filter": {"name": [name]}, "output": ["groupid"]})
    if result:
        return result[0]["groupid"]
    result = api.api("hostgroup.get", {"output": ["groupid"], "limit": 1})
    return result[0]["groupid"] if result else "2"


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap Zabbix monitoring (minimal first-run setup).\n"
                    "Ongoing config should be done via the Zabbix MCP server.\n"
                    "This script only handles: password change, host creation, media type, action."
    )
    parser.add_argument("--url", default=None, help="Zabbix URL (default: from ZABBIX_URL env or http://localhost:8084)")
    parser.add_argument("--user", default=None, help="Zabbix admin user (default: Admin)")
    parser.add_argument("--password", default=None, help="Initial admin password (default: zabbix)")
    parser.add_argument("--new-password", default=None, help="New admin password (from ZBX_ADMIN_PASSWORD env)")
    parser.add_argument("--pve-url", default=None, help="Proxmox VE API URL (from PVE_URL env)")
    parser.add_argument("--pve-node", default=None, help="Proxmox VE node name (from PVE_NODE env, default: pve)")
    parser.add_argument("--pve-token-id", default=None)
    parser.add_argument("--pve-token-secret", default=None)
    parser.add_argument("--agent-hostname", default=None)
    parser.add_argument("--agent-ip", default=None)
    parser.add_argument("--skip-init", action="store_true", help="Skip all init, just wait for UI and test login")
    args = parser.parse_args()

    url = args.url or os.environ.get("ZABBIX_URL", "http://localhost:8084")
    user = args.user or os.environ.get("ZABBIX_USER", "Admin")
    password = args.password or os.environ.get("ZABBIX_PASSWORD", "zabbix")
    new_password = args.new_password or os.environ.get("ZBX_ADMIN_PASSWORD", "")
    pve_url = args.pve_url or os.environ.get("PVE_URL", "")
    pve_node = args.pve_node or os.environ.get("PVE_NODE", "pve")
    pve_token_id = args.pve_token_id or os.environ.get("PVE_TOKEN_ID", "")
    pve_token_secret = args.pve_token_secret or os.environ.get("PVE_TOKEN_SECRET", "")
    agent_hostname = args.agent_hostname or os.environ.get("AGENT_HOSTNAME", "") or socket.getfqdn()
    agent_ip = args.agent_ip or os.environ.get("AGENT_IP", "")

    if not agent_ip:
        # Try to detect host IP (default route gateway, then first interface IP)
        try:
            agent_ip = os.popen("ip route show default 2>/dev/null | awk '{print $3}' | head -1").read().strip()
        except Exception:
            agent_ip = "127.0.0.1"
        if not agent_ip:
            agent_ip = "127.0.0.1"

    print("=" * 50)
    print("Zabbix Monitoring Stack — First-Run Bootstrap")
    print("=" * 50)
    print("This script handles minimal first-run setup only.")
    print("Ongoing config (hosts, templates, actions) should use the Zabbix MCP server.")
    print("=" * 50)

    if not wait_for_ui(url):
        sys.exit(1)

    if args.skip_init:
        print("Skip-init flag set. Testing API login only...")
        api = ZabbixAPI(url, user, password)
        token = api.login()
        if token:
            print("Login successful. Zabbix is ready for MCP-driven configuration.")
            api.logout()
        else:
            print("ERROR: Login failed.")
            sys.exit(1)
        sys.exit(0)

    api = ZabbixAPI(url, user, password)
    token = api.login()
    if not token:
        print("ERROR: Failed to login. Check credentials.")
        sys.exit(1)
    print(f"Logged in.")

    if new_password:
        change_password(api, new_password)

    hypervisors_gid = _get_group_id(api, "Hypervisors")
    linux_gid = _get_group_id(api, "Linux servers")

    if args.pve_url:
        create_proxmox_host(api, args.pve_url, args.pve_token_id or "", args.pve_token_secret or "", hypervisors_gid)

    if args.agent_hostname:
        create_agent_host(api, args.agent_hostname, args.agent_ip or "127.0.0.1", linux_gid)

    fix_zabbix_server_ip(api, args.agent_ip or "127.0.0.1")

    mt_id = create_matrix_media_type(api, url)
    if mt_id:
        add_admin_media(api, mt_id)
        create_trigger_action(api, mt_id)

    api.logout()
    print("\n" + "=" * 50)
    print("First-Run Bootstrap Complete!")
    print("=" * 50)
    print(f"Zabbix UI: {url}")
    print(f"Admin: {user} / {new_password or password}")
    print("")
    print("Ongoing management should use the Zabbix MCP server:")
    print("  zabbix_api       — execute any Zabbix API method")
    print("  zabbix_api_docs   — get API method documentation")
    print("  zabbix_api_list   — discover available API objects")
    print("")
    print("Next: Install agent2 on VMs with scripts/install-zabbix-agent2.sh")


if __name__ == "__main__":
    main()