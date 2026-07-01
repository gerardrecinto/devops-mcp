import json
import sys


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _fresh_snow():
    sys.modules.pop("devops_mcp.tools.servicenow", None)
    import importlib

    return importlib.import_module("devops_mcp.tools.servicenow")


def test_list_incidents_demo_returns_incidents(no_audit):
    snow = _fresh_snow()
    mcp = _FakeMCP()
    snow.register(mcp, no_audit)

    result = json.loads(mcp.tools["snow_list_incidents"]())
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["number"].startswith("INC")


def test_get_incident_demo_returns_details(no_audit):
    snow = _fresh_snow()
    mcp = _FakeMCP()
    snow.register(mcp, no_audit)

    result = json.loads(mcp.tools["snow_get_incident"](number="INC0045231"))
    assert result["number"] == "INC0045231"
    assert "description" in result
    assert "priority" in result


def test_get_change_requests_demo_returns_changes(no_audit):
    snow = _fresh_snow()
    mcp = _FakeMCP()
    snow.register(mcp, no_audit)

    result = json.loads(mcp.tools["snow_get_change_requests"]())
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["number"].startswith("CHG")
