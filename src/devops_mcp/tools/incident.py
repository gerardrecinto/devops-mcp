"""Cross-system incident timeline: one ordered view of changes and failures.

Reads through the other tool modules, so it needs no credentials of its own and
stays read-only. Correlation is by time proximity only; the output says so.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

Event = dict[str, Any]

# A change is only a candidate cause if it landed this long before the first failure.
MAX_SUSPECT_GAP = timedelta(hours=2)


def parse_ts(value: Any) -> datetime | None:
    """Parse ISO-8601, ServiceNow "YYYY-MM-DD HH:MM:SS" (UTC) or epoch milliseconds."""
    if value in (None, "", 0):
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, UTC)
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def build_timeline(
    events: list[Event], now: datetime, window: timedelta
) -> list[Event]:
    """Events inside the window, oldest first."""
    start = now - window
    return sorted((e for e in events if start <= e["ts"] <= now), key=lambda e: e["ts"])


def find_suspects(timeline: list[Event]) -> list[Event]:
    """Changes that landed shortly before the first failure, nearest first."""
    failures = [e for e in timeline if e["kind"] in ("failure", "incident")]
    if not failures:
        return []
    first = failures[0]
    near = [
        c
        for c in timeline
        if c["kind"] == "change"
        and timedelta(0) <= first["ts"] - c["ts"] <= MAX_SUSPECT_GAP
    ]
    return [
        {
            "change": c["summary"],
            "source": c["source"],
            "ref": c.get("ref", ""),
            "minutes_before_first_failure": int(
                (first["ts"] - c["ts"]).total_seconds() // 60
            ),
            "first_failure": first["summary"],
        }
        for c in sorted(near, key=lambda c: c["ts"], reverse=True)
    ]


def _rows(raw: str) -> tuple[list[dict[str, Any]] | None, str]:
    """Decode a tool result into rows, or explain why it can't be used."""
    try:
        body = json.loads(raw)
    except (TypeError, ValueError):
        return None, str(raw)[:120]
    if isinstance(body, dict) and body.get("demo"):
        return None, "demo data excluded"
    if isinstance(body, dict) and "error" in body:
        return None, str(body["error"])[:120]
    if isinstance(body, dict):
        return [body], ""
    return (body, "") if isinstance(body, list) else (None, "unexpected output shape")


def _snow_changes(rows: list[dict[str, Any]]) -> list[Event]:
    return [
        {
            "ts": ts,
            "source": "servicenow",
            "kind": "change",
            "summary": f"{r.get('number', '')} {r.get('short_description', '')}".strip(),
            "ref": r.get("number", ""),
        }
        for r in rows
        if (ts := parse_ts(r.get("start_date")))
    ]


def _snow_incidents(rows: list[dict[str, Any]]) -> list[Event]:
    return [
        {
            "ts": ts,
            "source": "servicenow",
            "kind": "incident",
            "summary": f"{r.get('number', '')} {r.get('short_description', '')}".strip(),
            "ref": r.get("number", ""),
        }
        for r in rows
        if (ts := parse_ts(r.get("opened_at")))
    ]


def _gh_failures(rows: list[dict[str, Any]]) -> list[Event]:
    return [
        {
            "ts": ts,
            "source": "github_actions",
            "kind": "failure",
            "summary": f"workflow {r.get('name', '')} failed at commit {r.get('commit', '')}",
            "ref": r.get("commit", ""),
        }
        for r in rows
        if (ts := parse_ts(r.get("created_at")))
    ]


def _k8s_warnings(rows: list[dict[str, Any]]) -> list[Event]:
    return [
        {
            "ts": ts,
            "source": "kubernetes",
            "kind": "failure",
            "summary": f"{r.get('reason', '')} on {r.get('object', '')}: {r.get('message', '')}",
            "ref": r.get("object", ""),
        }
        for r in rows
        if r.get("type") == "Warning" and (ts := parse_ts(r.get("last_seen")))
    ]


def _jenkins_build(rows: list[dict[str, Any]]) -> list[Event]:
    return [
        {
            "ts": ts,
            "source": "jenkins",
            "kind": "failure",
            "summary": f"{r.get('job', 'build')} #{r.get('build', '')} {r.get('result')}",
            "ref": str(r.get("build", "")),
        }
        for r in rows
        if r.get("result") in ("FAILURE", "UNSTABLE")
        and (ts := parse_ts(r.get("timestamp")))
    ]


def register(
    mcp: Any, audit: Callable[[str, dict], None], tools: dict[str, Callable[..., str]]
) -> None:
    @mcp.tool()
    def incident_timeline(
        hours: int = 6,
        namespace: str = "",
        owner: str = "",
        repo: str = "",
        job_name: str = "",
    ) -> str:
        """One ordered timeline of changes, CI failures, cluster warnings and incidents.

        Lists the changes that landed shortly before the first failure as suspects.
        namespace, owner/repo and job_name opt in to Kubernetes, GitHub Actions and
        Jenkins; ServiceNow is always queried. Correlation is by time only.
        """
        audit(
            "incident_timeline",
            {
                "hours": hours,
                "namespace": namespace,
                "owner": owner,
                "repo": repo,
                "job": job_name,
            },
        )
        hours = min(max(hours, 1), 168)
        now = datetime.now(UTC)
        plan: list[
            tuple[
                str, str, dict[str, Any], Callable[[list[dict[str, Any]]], list[Event]]
            ]
        ] = [
            (
                "servicenow changes",
                "snow_get_change_requests",
                {"state": "implement", "limit": 25},
                _snow_changes,
            ),
            (
                "servicenow incidents",
                "snow_list_incidents",
                {"state": "open", "limit": 25},
                _snow_incidents,
            ),
        ]
        if namespace:
            plan.append(
                (
                    "kubernetes",
                    "k8s_get_events",
                    {"namespace": namespace},
                    _k8s_warnings,
                )
            )
        if owner and repo:
            plan.append(
                (
                    "github actions",
                    "gh_list_failed_runs",
                    {"owner": owner, "repo": repo},
                    _gh_failures,
                )
            )
        if job_name:
            plan.append(
                (
                    "jenkins",
                    "jenkins_get_build_status",
                    {"job_name": job_name},
                    _jenkins_build,
                )
            )

        events: list[Event] = []
        sources: dict[str, str] = {}
        for label, tool, kwargs, normalize in plan:
            fn = tools.get(tool)
            if fn is None:
                sources[label] = "skipped: module not loaded"
                continue
            try:
                rows, why = _rows(fn(**kwargs))
            except Exception as exc:  # noqa: BLE001
                sources[label] = f"skipped: {type(exc).__name__}: {str(exc)[:100]}"
                continue
            if rows is None:
                sources[label] = f"skipped: {why}"
                continue
            found = normalize(rows)
            events.extend(found)
            sources[label] = f"ok, {len(found)} event(s)"

        timeline = build_timeline(events, now, timedelta(hours=hours))
        return json.dumps(
            {
                "window_hours": hours,
                "generated_at": now.isoformat(),
                "sources": sources,
                "suspect_changes": find_suspects(timeline),
                "timeline": [{**e, "ts": e["ts"].isoformat()} for e in timeline],
                "caveat": (
                    "Suspects are changes that landed shortly before the first failure. "
                    "That is correlation by time, not proof of cause."
                ),
            },
            indent=2,
        )
