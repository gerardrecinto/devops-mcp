from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests as _requests


def _get_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    resp = _requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    tenant_id = os.getenv("TEAMS_TENANT_ID", "")
    client_id = os.getenv("TEAMS_CLIENT_ID", "")
    client_secret = os.getenv("TEAMS_CLIENT_SECRET", "")
    default_webhook = os.getenv("TEAMS_WEBHOOK_URL", "")
    has_graph = bool(tenant_id and client_id and client_secret)

    if not has_graph and not default_webhook:

        @mcp.tool()
        def teams_post_message(  # type: ignore[misc]
            title: str,
            text: str,
            color: str = "0076D7",
            webhook_url: str = "",
        ) -> str:
            """Post an alert card to a Teams channel via webhook. (demo mode -- TEAMS_WEBHOOK_URL not configured)"""
            audit("teams_post_message", {"title": title})
            return json.dumps({"ok": True, "status": 200})

        @mcp.tool()
        def teams_get_channel_messages(  # type: ignore[misc]
            team_id: str,
            channel_id: str,
            hours: int = 1,
        ) -> str:
            """Fetch recent messages from a Teams channel. (demo mode)"""
            audit("teams_get_channel_messages", {"team_id": team_id, "channel_id": channel_id})
            return json.dumps([
                {"id": "1705305480000", "from": "Jane Smith", "created": "2024-01-15T09:08:00Z", "body": "prod api is throwing 502s, is anyone looking at this?"},
                {"id": "1705305540000", "from": "oncall-bot", "created": "2024-01-15T09:09:00Z", "body": "[ALERT] api-gateway error rate 18% (threshold: 1%)"},
                {"id": "1705305600000", "from": "Gerard Recinto", "created": "2024-01-15T09:10:00Z", "body": "on it, checking K8s events now"},
            ], indent=2)

        @mcp.tool()
        def teams_list_channels(  # type: ignore[misc]
            team_id: str,
        ) -> str:
            """List channels in a Microsoft Teams team. (demo mode)"""
            audit("teams_list_channels", {"team_id": team_id})
            return json.dumps([
                {"id": "19:abc123@thread.tacv2", "name": "General", "description": ""},
                {"id": "19:def456@thread.tacv2", "name": "incidents", "description": "Production incident coordination"},
                {"id": "19:ghi789@thread.tacv2", "name": "platform-alerts", "description": "Automated alerts from CI/CD and monitoring"},
            ], indent=2)

        return

    graph_base = "https://graph.microsoft.com/v1.0"

    @mcp.tool()
    def teams_post_message(
        title: str,
        text: str,
        color: str = "0076D7",
        webhook_url: str = "",
    ) -> str:
        """Post an alert card to a Teams channel via incoming webhook."""
        audit("teams_post_message", {"title": title})
        url = webhook_url or default_webhook
        if not url:
            return json.dumps({"error": "No webhook URL provided and TEAMS_WEBHOOK_URL is not set."})
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [{"activityTitle": title, "activityText": text}],
        }
        resp = _requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return json.dumps({"ok": True, "status": resp.status_code})

    @mcp.tool()
    def teams_get_channel_messages(
        team_id: str,
        channel_id: str,
        hours: int = 1,
    ) -> str:
        """Fetch recent messages from a Microsoft Teams channel via Graph API."""
        audit("teams_get_channel_messages", {"team_id": team_id, "channel_id": channel_id})
        token = _get_graph_token(tenant_id, client_id, client_secret)
        headers = {"Authorization": f"Bearer {token}"}
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        url = f"{graph_base}/teams/{team_id}/channels/{channel_id}/messages"
        resp = _requests.get(url, headers=headers, params={"$top": 50}, timeout=15)
        resp.raise_for_status()
        messages = [
            {
                "id": m["id"],
                "from": m.get("from", {}).get("user", {}).get("displayName", ""),
                "created": m.get("createdDateTime", ""),
                "body": m.get("body", {}).get("content", ""),
            }
            for m in resp.json().get("value", [])
            if m.get("messageType") == "message" and m.get("createdDateTime", "") >= cutoff
        ]
        return json.dumps(messages, indent=2)

    @mcp.tool()
    def teams_list_channels(team_id: str) -> str:
        """List all channels in a Microsoft Teams team."""
        audit("teams_list_channels", {"team_id": team_id})
        token = _get_graph_token(tenant_id, client_id, client_secret)
        headers = {"Authorization": f"Bearer {token}"}
        resp = _requests.get(f"{graph_base}/teams/{team_id}/channels", headers=headers, timeout=15)
        resp.raise_for_status()
        return json.dumps([
            {"id": c["id"], "name": c["displayName"], "description": c.get("description", "")}
            for c in resp.json().get("value", [])
        ], indent=2)
