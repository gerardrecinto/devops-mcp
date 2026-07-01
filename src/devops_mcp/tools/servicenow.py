from __future__ import annotations

import json
import os
from typing import Any, Callable

import requests


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    instance = os.getenv("SNOW_INSTANCE", "")
    user = os.getenv("SNOW_USER", "")
    password = os.getenv("SNOW_PASSWORD", "")

    if not instance:

        @mcp.tool()
        def snow_list_incidents(  # type: ignore[misc]
            state: str = "open",
            limit: int = 10,
            assigned_to: str = "",
        ) -> str:
            """List ServiceNow incidents. (demo mode -- SNOW_INSTANCE not configured)"""
            audit("snow_list_incidents", {"state": state})
            return json.dumps(
                [
                    {
                        "number": "INC0045231",
                        "short_description": "API gateway 502 errors spiking",
                        "priority": "1 - Critical",
                        "state": "In Progress",
                        "assigned_to": "oncall-sre",
                        "opened_at": "2024-01-15T08:52:00Z",
                    },
                    {
                        "number": "INC0045198",
                        "short_description": "Build pipeline stuck: artifact upload timeout",
                        "priority": "2 - High",
                        "state": "New",
                        "assigned_to": "",
                        "opened_at": "2024-01-15T07:30:00Z",
                    },
                    {
                        "number": "INC0045102",
                        "short_description": "K8s node NotReady: node-4 disk pressure",
                        "priority": "2 - High",
                        "state": "In Progress",
                        "assigned_to": "platform-team",
                        "opened_at": "2024-01-15T06:10:00Z",
                    },
                ],
                indent=2,
            )

        @mcp.tool()
        def snow_get_incident(number: str) -> str:  # type: ignore[misc]
            """Get a ServiceNow incident by number. (demo mode)"""
            audit("snow_get_incident", {"number": number})
            return json.dumps(
                {
                    "number": number,
                    "short_description": "API gateway 502 errors spiking",
                    "description": "Starting at 08:50 UTC, error rate on the API gateway climbed from 0.1% to 18%. Downstream services reporting connection timeouts.",
                    "priority": "1 - Critical",
                    "state": "In Progress",
                    "assigned_to": "oncall-sre",
                    "opened_at": "2024-01-15T08:52:00Z",
                    "updated_at": "2024-01-15T09:05:00Z",
                    "resolution_notes": "",
                },
                indent=2,
            )

        @mcp.tool()
        def snow_get_change_requests(  # type: ignore[misc]
            state: str = "scheduled",
            limit: int = 10,
        ) -> str:
            """List ServiceNow change requests. (demo mode)"""
            audit("snow_get_change_requests", {"state": state})
            return json.dumps(
                [
                    {
                        "number": "CHG0012481",
                        "short_description": "Upgrade K8s 1.29 to 1.30 on prod cluster",
                        "state": "Scheduled",
                        "risk": "Moderate",
                        "start_date": "2024-01-20T02:00:00Z",
                        "end_date": "2024-01-20T05:00:00Z",
                    },
                    {
                        "number": "CHG0012450",
                        "short_description": "MSK Kafka broker scale-out: 6 to 9 brokers",
                        "state": "Scheduled",
                        "risk": "Low",
                        "start_date": "2024-01-18T22:00:00Z",
                        "end_date": "2024-01-18T23:30:00Z",
                    },
                ],
                indent=2,
            )

        return

    base_url = f"https://{instance}/api/now"
    auth = (user, password)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    STATE_MAP = {
        "open": "1,2,3",
        "new": "1",
        "in_progress": "2",
        "on_hold": "3",
        "resolved": "6",
        "closed": "7",
    }

    CHANGE_STATE_MAP = {
        "scheduled": "-1",
        "implement": "1",
        "review": "2",
        "closed": "3",
    }

    @mcp.tool()
    def snow_list_incidents(
        state: str = "open",
        limit: int = 10,
        assigned_to: str = "",
    ) -> str:
        """List ServiceNow incidents filtered by state and optionally by assignee."""
        audit(
            "snow_list_incidents",
            {"state": state, "limit": limit, "assigned_to": assigned_to},
        )
        state_val = STATE_MAP.get(state, "1,2,3")
        query = f"active=true^stateIN{state_val}^ORDERBYDESCpriority"
        if assigned_to:
            query += f"^assigned_to.name={assigned_to}"
        params: dict[str, Any] = {
            "sysparm_query": query,
            "sysparm_limit": limit,
            "sysparm_fields": "number,short_description,priority,state,assigned_to,opened_at",
        }
        resp = requests.get(
            f"{base_url}/table/incident",
            auth=auth,
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])
        return json.dumps(
            [
                {
                    "number": r["number"],
                    "short_description": r["short_description"],
                    "priority": r["priority"],
                    "state": r["state"],
                    "assigned_to": (
                        r.get("assigned_to", {}).get("display_value", "")
                        if isinstance(r.get("assigned_to"), dict)
                        else r.get("assigned_to", "")
                    ),
                    "opened_at": r["opened_at"],
                }
                for r in records
            ],
            indent=2,
        )

    @mcp.tool()
    def snow_get_incident(number: str) -> str:
        """Get a specific ServiceNow incident by number (e.g. INC0012345)."""
        audit("snow_get_incident", {"number": number})
        params = {
            "sysparm_query": f"number={number}",
            "sysparm_limit": 1,
            "sysparm_fields": "number,short_description,description,priority,state,assigned_to,opened_at,sys_updated_on,close_notes",
        }
        resp = requests.get(
            f"{base_url}/table/incident",
            auth=auth,
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])
        if not records:
            return json.dumps({"error": f"Incident {number} not found."})
        r = records[0]
        return json.dumps(
            {
                "number": r["number"],
                "short_description": r["short_description"],
                "description": r["description"],
                "priority": r["priority"],
                "state": r["state"],
                "assigned_to": (
                    r.get("assigned_to", {}).get("display_value", "")
                    if isinstance(r.get("assigned_to"), dict)
                    else r.get("assigned_to", "")
                ),
                "opened_at": r["opened_at"],
                "updated_at": r["sys_updated_on"],
                "resolution_notes": r.get("close_notes", ""),
            },
            indent=2,
        )

    @mcp.tool()
    def snow_get_change_requests(
        state: str = "scheduled",
        limit: int = 10,
    ) -> str:
        """List ServiceNow change requests by state (scheduled, implement, review, closed)."""
        audit("snow_get_change_requests", {"state": state, "limit": limit})
        state_val = CHANGE_STATE_MAP.get(state, "-1")
        params = {
            "sysparm_query": f"state={state_val}^ORDERBYstart_date",
            "sysparm_limit": limit,
            "sysparm_fields": "number,short_description,state,risk,start_date,end_date,assigned_to,type",
        }
        resp = requests.get(
            f"{base_url}/table/change_request",
            auth=auth,
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])
        return json.dumps(
            [
                {
                    "number": r["number"],
                    "short_description": r["short_description"],
                    "state": r["state"],
                    "risk": r.get("risk", ""),
                    "type": r.get("type", ""),
                    "start_date": r.get("start_date", ""),
                    "end_date": r.get("end_date", ""),
                    "assigned_to": (
                        r.get("assigned_to", {}).get("display_value", "")
                        if isinstance(r.get("assigned_to"), dict)
                        else r.get("assigned_to", "")
                    ),
                }
                for r in records
            ],
            indent=2,
        )
