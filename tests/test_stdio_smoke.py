import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _list_tools(home: str) -> set[str]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "devops_mcp.server"],
        env={"HOME": home, "DEVOPS_MCP_DEMO": "1", "PATH": ""},
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.list_tools()
        return {t.name for t in result.tools}


def test_server_starts_over_stdio_and_lists_tools(tmp_path):
    names = asyncio.run(asyncio.wait_for(_list_tools(str(tmp_path)), timeout=60))
    assert "k8s_get_failing_pods" in names
    assert "incident_timeline" in names
    assert "devops_mcp_health" in names
