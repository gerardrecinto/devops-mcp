from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        from slack_sdk import WebClient  # type: ignore

        client = WebClient(token=os.getenv("SLACK_BOT_TOKEN", ""))

        @mcp.tool()
        def slack_post_message(channel: str, text: str) -> str:
            """Post a message to a Slack channel or user (for incident alerts)."""
            audit("slack_post_message", {"channel": channel})
            resp = client.chat_postMessage(channel=channel, text=text)
            return json.dumps({"ok": resp["ok"], "ts": resp["ts"], "channel": resp["channel"]})

        @mcp.tool()
        def slack_get_channel_history(channel: str, hours: int = 1) -> str:
            """Fetch recent messages from a Slack channel."""
            audit("slack_get_channel_history", {"channel": channel, "hours": hours})
            oldest = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
            resp = client.conversations_history(channel=channel, oldest=str(oldest), limit=50)
            messages = [
                {
                    "ts": m["ts"],
                    "user": m.get("user", m.get("bot_id", "unknown")),
                    "text": m.get("text", ""),
                }
                for m in resp.get("messages", [])
                if m.get("type") == "message"
            ]
            return json.dumps(messages, indent=2)

        @mcp.tool()
        def slack_search_messages(query: str, count: int = 10) -> str:
            """Search Slack messages across all channels (requires search:read scope)."""
            audit("slack_search_messages", {"query": query, "count": count})
            resp = client.search_messages(query=query, count=count)
            matches = resp.get("messages", {}).get("matches", [])
            return json.dumps([
                {
                    "channel": m.get("channel", {}).get("name", ""),
                    "ts": m.get("ts", ""),
                    "user": m.get("username", ""),
                    "text": m.get("text", ""),
                    "permalink": m.get("permalink", ""),
                }
                for m in matches
            ], indent=2)

    except ImportError:

        @mcp.tool()
        def slack_post_message(  # type: ignore[misc]
            channel: str,
            text: str,
        ) -> str:
            """Post a message to Slack. (demo mode -- slack-sdk not installed)"""
            audit("slack_post_message", {"channel": channel})
            return json.dumps({"ok": True, "ts": "1705305600.123456", "channel": channel})

        @mcp.tool()
        def slack_get_channel_history(  # type: ignore[misc]
            channel: str,
            hours: int = 1,
        ) -> str:
            """Fetch recent Slack messages. (demo mode)"""
            audit("slack_get_channel_history", {"channel": channel, "hours": hours})
            return json.dumps([
                {"ts": "1705305480.000100", "user": "U01234ABC", "text": "prod api latency is spiking, looking into it"},
                {"ts": "1705305540.000200", "user": "U05678DEF", "text": "confirmed, cloudwatch shows db connections at 97%"},
                {"ts": "1705305600.000300", "user": "U01234ABC", "text": "db-prod-0 OOMKilled, restarting now"},
            ], indent=2)

        @mcp.tool()
        def slack_search_messages(  # type: ignore[misc]
            query: str,
            count: int = 10,
        ) -> str:
            """Search Slack messages. (demo mode)"""
            audit("slack_search_messages", {"query": query, "count": count})
            return json.dumps([
                {"channel": "incidents", "ts": "1705305480.000100", "user": "oncall-bot", "text": f"[ALERT] {query} triggered P1 threshold", "permalink": "https://slack.com/archives/C001/p1705305480000100"},
                {"channel": "platform", "ts": "1704700000.000200", "user": "gerard", "text": f"investigated {query} last week, fix is in deploy pipeline", "permalink": "https://slack.com/archives/C002/p1704700000000200"},
            ], indent=2)
