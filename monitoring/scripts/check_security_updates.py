#!/usr/bin/env python3
"""Check Proxmox VE nodes for security/CVE-related APT updates.

Supports two backends:
  1. PVE direct (default) — calls Proxmox VE HTTPS API directly
  2. HP MCP — calls HomePilot MCP API (requires HP_MCP_TOKEN)

Outputs JSON suitable for Zabbix external checks or cron-based monitoring.

Architecture:
    PVE direct: cron/Zabbix → this script → PVE HTTPS API
    HP MCP:      cron/Zabbix → this script → HomePilot REST API → PVE MCP → PVE nodes

Usage:
    # Single node (PVE direct)
    python3 check_security_updates.py --node pve

    # All nodes (PVE direct)
    python3 check_security_updates.py --all

    # Using HomePilot MCP backend
    python3 check_security_updates.py --all --backend hp

    # Zabbix mode (exit 1 if security updates found)
    python3 check_security_updates.py --node pve --zabbix

    # Refresh update cache first
    python3 check_security_updates.py --node pve --refresh

Environment (PVE direct — default):
    PVE_HOST       — PVE hostname/IP (default: pve.example.local)
    PVE_PORT       — PVE port (default: 8006)
    PVE_TOKEN_ID   — PVE API token ID (e.g. root@pam!security-cron)
    PVE_TOKEN_SECRET — PVE API token secret

Environment (HP MCP backend):
    HP_API_URL     — HomePilot REST API base URL (default: http://your-server.local:8000)
    HP_API_TOKEN   — Bearer token for HomePilot MCP API
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import argparse
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Any


CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
DSA_PATTERN = re.compile(r"DSA[_-]\d+[-\d]*", re.IGNORECASE)
USN_PATTERN = re.compile(r"USN-\d+[-\d]*", re.IGNORECASE)
SECURITY_KEYWORDS = re.compile(
    r"\b(security|vulnerability|cve|dsa|usn|exploit|advisory|patched|fixed\s+vuln)"
    r"\b",
    re.IGNORECASE,
)


# ── PVE Direct API Backend ──────────────────────────────────────────

def get_pve_config() -> tuple[str, int, str, str, ssl.SSLContext | None]:
    host = os.environ.get("PVE_HOST", "pve.example.local")
    port = int(os.environ.get("PVE_PORT", "8006"))
    token_id = os.environ.get("PVE_TOKEN_ID", "")
    token_secret = os.environ.get("PVE_TOKEN_SECRET", "")
    verify = os.environ.get("PVE_VERIFY_SSL", "0") == "1"
    if not token_id or not token_secret:
        print("ERROR: PVE_TOKEN_ID and PVE_TOKEN_SECRET must be set", file=sys.stderr)
        sys.exit(2)
    ctx = None if verify else ssl._create_unverified_context()
    return host, port, token_id, token_secret, ctx


def pve_request(
    path: str,
    token_id: str,
    token_secret: str,
    method: str = "GET",
    data: bytes | None = None,
    host: str = "",
    port: int = 8006,
    ctx: ssl.SSLContext | None = None,
) -> Any:
    url = f"https://{host}:{port}/api2/json{path}"
    headers = {
        "Authorization": f"PVEAPIToken={token_id}={token_secret}",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"PVE HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"PVE connection error: {e.reason}", file=sys.stderr)
        return None


def pve_get_nodes(host: str, port: int, token_id: str, token_secret: str, ctx: ssl.SSLContext | None) -> list[str]:
    result = pve_request("/nodes", token_id, token_secret, host=host, port=port, ctx=ctx)
    if result and isinstance(result, dict) and "data" in result:
        return [n["node"] for n in result["data"] if "node" in n]
    return []


def pve_refresh_updates(node: str, host: str, port: int, token_id: str, token_secret: str, ctx: ssl.SSLContext | None) -> bool:
    result = pve_request(f"/nodes/{node}/apt/update", token_id, token_secret, method="POST", host=host, port=port, ctx=ctx)
    return result is not None


def pve_get_updates(node: str, host: str, port: int, token_id: str, token_secret: str, ctx: ssl.SSLContext | None) -> list[dict]:
    result = pve_request(f"/nodes/{node}/apt/updates", token_id, token_secret, host=host, port=port, ctx=ctx)
    if result and isinstance(result, dict) and "data" in result:
        return result["data"] if isinstance(result["data"], list) else []
    return []


def pve_get_changelog(node: str, pkg_name: str, version: str | None, host: str, port: int, token_id: str, token_secret: str, ctx: ssl.SSLContext | None) -> str:
    path = f"/nodes/{node}/apt/changelog?name={pkg_name}"
    if version:
        path += f"&version={version}"
    result = pve_request(path, token_id, token_secret, host=host, port=port, ctx=ctx)
    if result and isinstance(result, dict):
        if "data" in result and isinstance(result["data"], str):
            return result["data"]
        return json.dumps(result)
    return ""


# ── HP MCP API Backend ──────────────────────────────────────────────

def get_hp_config() -> tuple[str, str]:
    url = os.environ.get("HP_API_URL", "http://your-server.local:8000").rstrip("/")
    token = os.environ.get("HP_API_TOKEN", "")
    if not token:
        print("ERROR: HP_API_TOKEN not set", file=sys.stderr)
        sys.exit(2)
    return url, token


def hp_api_call(url: str, token: str, tool_name: str, args: dict | None = None) -> dict | list | None:
    endpoint = f"{url}/mcp/{tool_name}"
    payload = {"arguments": args or {}}
    data = json.dumps(payload).encode()
    req = Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            if isinstance(body, dict):
                for key in ("result", "data", "output", "content"):
                    if key in body:
                        val = body[key]
                        if isinstance(val, list):
                            return val
                        if isinstance(val, str):
                            try:
                                parsed = json.loads(val)
                                if isinstance(parsed, (dict, list)):
                                    return parsed
                            except json.JSONDecodeError:
                                pass
                        if isinstance(val, dict):
                            return val
                if "error" in body:
                    print(f"HP API error: {body['error']}", file=sys.stderr)
                    return None
                return body
            return body
    except HTTPError as e:
        print(f"HP HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"HP connection error: {e.reason}", file=sys.stderr)
        return None


# ── Shared Logic ────────────────────────────────────────────────────

def classify_severity(changelog: str) -> tuple[str, list[str]]:
    cve_refs = sorted(set(CVE_PATTERN.findall(changelog)))
    dsa_refs = sorted(set(DSA_PATTERN.findall(changelog)))
    usn_refs = sorted(set(USN_PATTERN.findall(changelog)))
    all_refs = cve_refs + dsa_refs + usn_refs

    if cve_refs:
        return "critical", all_refs
    if dsa_refs or usn_refs:
        return "high", all_refs
    if SECURITY_KEYWORDS.search(changelog):
        return "medium", all_refs
    return "low", all_refs


def check_node_pve(node: str, host: str, port: int, token_id: str, token_secret: str, ctx: ssl.SSLContext | None, do_refresh: bool = False) -> dict:
    if do_refresh:
        pve_refresh_updates(node, host, port, token_id, token_secret, ctx)

    updates = pve_get_updates(node, host, port, token_id, token_secret, ctx)
    security_packages = []
    total_updates = len(updates)

    for pkg in updates:
        name = pkg.get("Package", pkg.get("package", "unknown"))
        version = pkg.get("Version", pkg.get("version", "N/A"))
        old_version = pkg.get("OldVersion", pkg.get("oldversion", ""))
        description = pkg.get("Description", pkg.get("description", ""))

        changelog = pve_get_changelog(node, name, version, host, port, token_id, token_secret, ctx)
        severity, cve_refs = classify_severity(changelog)
        if not cve_refs and not SECURITY_KEYWORDS.search(description):
            if severity == "low" and not cve_refs:
                continue

        security_packages.append(
            {
                "name": name,
                "version": version,
                "old_version": old_version,
                "severity": severity,
                "cve_refs": cve_refs,
                "description": description[:200] if description else "",
            }
        )

    return {
        "node": node,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_updates": total_updates,
        "security_updates": len(security_packages),
        "packages": security_packages,
    }


def check_node_hp(url: str, token: str, node: str, do_refresh: bool = False) -> dict:
    if do_refresh:
        hp_api_call(url, token, "proxmox_refresh_apt_updates", {"node": node})

    result = hp_api_call(url, token, "proxmox_list_apt_updates", {"node": node})
    updates = result if isinstance(result, list) else []
    security_packages = []
    total_updates = len(updates)

    for pkg in updates:
        name = pkg.get("Package", pkg.get("package", "unknown"))
        version = pkg.get("Version", pkg.get("version", "N/A"))
        old_version = pkg.get("OldVersion", pkg.get("oldversion", ""))
        description = pkg.get("Description", pkg.get("description", ""))

        args: dict[str, Any] = {"node": node, "name": name}
        if version != "N/A":
            args["version"] = version
        changelog_result = hp_api_call(url, token, "proxmox_list_apt_changelog", args)
        changelog = ""
        if isinstance(changelog_result, dict):
            for key in ("result", "data", "output", "content"):
                if key in changelog_result and isinstance(changelog_result[key], str):
                    changelog = changelog_result[key]
                    break
        elif isinstance(changelog_result, str):
            changelog = changelog_result

        severity, cve_refs = classify_severity(changelog)
        if not cve_refs and not SECURITY_KEYWORDS.search(description):
            if severity == "low" and not cve_refs:
                continue

        security_packages.append(
            {
                "name": name,
                "version": version,
                "old_version": old_version,
                "severity": severity,
                "cve_refs": cve_refs,
                "description": description[:200] if description else "",
            }
        )

    return {
        "node": node,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_updates": total_updates,
        "security_updates": len(security_packages),
        "packages": security_packages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check PVE security updates")
    parser.add_argument("--node", help="Specific PVE node name")
    parser.add_argument("--all", action="store_true", help="Check all PVE nodes")
    parser.add_argument("--refresh", action="store_true", help="Refresh APT cache before checking")
    parser.add_argument("--zabbix", action="store_true", help="Zabbix mode: exit 1 if security updates found")
    parser.add_argument("--backend", choices=["pve", "hp"], default="pve", help="API backend: pve (direct) or hp (HomePilot MCP)")
    args = parser.parse_args()

    if not args.node and not args.all:
        args.all = True

    if args.backend == "pve":
        host, port, token_id, token_secret, ctx = get_pve_config()
        nodes = [args.node] if args.node else pve_get_nodes(host, port, token_id, token_secret, ctx)
        if not nodes:
            print(json.dumps({"error": "No nodes found"}))
            sys.exit(2)
        results = []
        total_security = 0
        for node in nodes:
            result = check_node_pve(node, host, port, token_id, token_secret, ctx, do_refresh=args.refresh)
            results.append(result)
            total_security += result["security_updates"]
    else:
        url, token = get_hp_config()
        nodes = [args.node] if args.node else hp_api_call(url, token, "proxmox_list_nodes", {}) or []
        node_names = []
        if not args.node:
            if isinstance(nodes, list):
                node_names = [n.get("node", n.get("name", "")) for n in nodes if isinstance(n, dict)]
            if not node_names:
                print(json.dumps({"error": "No nodes found"}))
                sys.exit(2)
        else:
            node_names = [args.node]
        results = []
        total_security = 0
        for node in node_names:
            result = check_node_hp(url, token, node, do_refresh=args.refresh)
            results.append(result)
            total_security += result["security_updates"]

    output = results if len(results) > 1 else results[0]
    print(json.dumps(output, indent=2))

    if args.zabbix and total_security > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()