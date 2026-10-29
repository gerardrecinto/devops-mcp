import asyncio
import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
PREFIXES = (
    "k8s_",
    "jenkins_",
    "gh_",
    "aws_",
    "azure_",
    "gcp_",
    "snow_",
    "slack_",
    "teams_",
    "incident_",
    "devops_mcp_",
)


def _registered(tmp_path, monkeypatch) -> set[str]:
    from devops_mcp import server

    monkeypatch.setattr(server.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(server.mcp, "run", lambda: None)
    server.main()
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


def _documented() -> set[str]:
    names = set(re.findall(r"^\| `([a-z0-9_]+)` \|", README.read_text(), re.MULTILINE))
    return {n for n in names if n.startswith(PREFIXES)}


def test_readme_tools_exist(tmp_path, monkeypatch):
    missing = _documented() - _registered(tmp_path, monkeypatch)
    assert not missing, f"README lists tools that are not registered: {missing}"


def test_every_tool_is_in_readme(tmp_path, monkeypatch):
    undocumented = _registered(tmp_path, monkeypatch) - _documented()
    assert not undocumented, f"tools missing from README: {undocumented}"
