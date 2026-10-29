import json
from datetime import UTC, datetime, timedelta

from devops_mcp.tools import incident

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _ev(minutes_ago, kind, summary="x", source="s"):
    return {
        "ts": NOW - timedelta(minutes=minutes_ago),
        "kind": kind,
        "summary": summary,
        "source": source,
    }


def test_parse_ts_formats():
    assert incident.parse_ts("2026-10-28T12:00:00Z") == NOW
    assert incident.parse_ts("2026-10-28 12:00:00") == NOW
    assert incident.parse_ts(int(NOW.timestamp() * 1000)) == NOW
    assert incident.parse_ts("") is None
    assert incident.parse_ts("not a date") is None


def test_timeline_is_windowed_and_ordered():
    events = [
        _ev(10, "failure"),
        _ev(300, "change"),
        _ev(50, "change"),
        _ev(-5, "failure"),
    ]
    out = incident.build_timeline(events, NOW, timedelta(hours=2))
    assert [e["kind"] for e in out] == ["change", "failure"]
    assert out[0]["ts"] < out[1]["ts"]


def test_suspect_is_change_shortly_before_first_failure():
    tl = incident.build_timeline(
        [
            _ev(90, "change", "CHG1"),
            _ev(20, "change", "CHG2"),
            _ev(10, "failure", "pod crash"),
        ],
        NOW,
        timedelta(hours=6),
    )
    out = incident.find_suspects(tl)
    assert [s["change"] for s in out] == ["CHG2", "CHG1"]
    assert out[0]["minutes_before_first_failure"] == 10


def test_change_after_failure_or_too_old_is_not_suspect():
    tl = incident.build_timeline(
        [_ev(300, "change", "old"), _ev(60, "failure"), _ev(5, "change", "after")],
        NOW,
        timedelta(hours=12),
    )
    assert incident.find_suspects(tl) == []


def test_no_failures_means_no_suspects():
    assert incident.find_suspects([_ev(5, "change")]) == []


class _MCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        return lambda fn: self.tools.setdefault(fn.__name__, fn)


def _run(tools, no_audit, **kwargs):
    mcp = _MCP()
    incident.register(mcp, no_audit, tools)
    return json.loads(mcp.tools["incident_timeline"](**kwargs))


def test_end_to_end_across_sources_with_one_broken(no_audit):
    now = datetime.now(UTC)
    change = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    event_ts = (now - timedelta(minutes=10)).isoformat()

    def boom(**_):
        raise RuntimeError("connection refused")

    tools = {
        "snow_get_change_requests": lambda **_: json.dumps(
            [
                {
                    "number": "CHG1",
                    "short_description": "raise db limits",
                    "start_date": change,
                }
            ]
        ),
        "snow_list_incidents": boom,
        "k8s_get_events": lambda **_: json.dumps(
            [
                {
                    "type": "Warning",
                    "reason": "OOMKilling",
                    "object": "Pod/db-0",
                    "message": "limit",
                    "last_seen": event_ts,
                }
            ]
        ),
    }
    out = _run(tools, no_audit, namespace="prod")
    assert out["sources"]["servicenow changes"].startswith("ok")
    assert out["sources"]["servicenow incidents"].startswith("skipped: RuntimeError")
    assert out["sources"]["kubernetes"].startswith("ok")
    assert out["suspect_changes"][0]["change"].startswith("CHG1")
    assert "not proof" in out["caveat"]


def test_unconfigured_and_demo_sources_are_skipped_not_invented(no_audit):
    tools = {
        "snow_get_change_requests": lambda **_: json.dumps(
            {"error": "ServiceNow is not configured"}
        ),
        "snow_list_incidents": lambda **_: json.dumps(
            {"demo": True, "data": [{"number": "INC1"}]}
        ),
    }
    out = _run(tools, no_audit)
    assert out["timeline"] == []
    assert all(v.startswith("skipped") for v in out["sources"].values())


def test_optional_sources_only_when_requested(no_audit):
    out = _run({}, no_audit)
    assert set(out["sources"]) == {"servicenow changes", "servicenow incidents"}
    out = _run({}, no_audit, namespace="p", owner="o", repo="r", job_name="j")
    assert {"kubernetes", "github actions", "jenkins"} <= set(out["sources"])
