from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from devops_mcp.demo import demo_tool


def _base() -> str:
    return os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/") + "/api/v4"


def _project(path: str) -> str:
    """GitLab wants the project path as one URL-encoded segment, e.g. group%2Fapp."""
    return quote(path, safe="")


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        import requests  # type: ignore

        def _headers() -> dict[str, str]:
            token = os.getenv("GITLAB_TOKEN", "")
            return {"PRIVATE-TOKEN": token} if token else {}

        @mcp.tool()
        def gl_get_pipeline(project: str, pipeline_id: int) -> str:
            """Get one GitLab CI pipeline. project is the path, for example group/app."""
            audit("gl_get_pipeline", {"project": project, "pipeline_id": pipeline_id})
            resp = requests.get(
                f"{_base()}/projects/{_project(project)}/pipelines/{pipeline_id}",
                headers=_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            d = resp.json()
            return json.dumps(
                {
                    "id": d["id"],
                    "status": d["status"],
                    "ref": d["ref"],
                    "commit": d["sha"][:8],
                    "duration_seconds": d.get("duration"),
                    "created_at": d["created_at"],
                    "url": d["web_url"],
                },
                indent=2,
            )

        @mcp.tool()
        def gl_list_failed_pipelines(project: str, limit: int = 10) -> str:
            """List recent failed GitLab CI pipelines for a project."""
            audit("gl_list_failed_pipelines", {"project": project, "limit": limit})
            resp = requests.get(
                f"{_base()}/projects/{_project(project)}/pipelines",
                headers=_headers(),
                params={"status": "failed", "per_page": limit},
                timeout=10,
            )
            resp.raise_for_status()
            return json.dumps(
                [
                    {
                        "id": p["id"],
                        "ref": p["ref"],
                        "commit": p["sha"][:8],
                        "created_at": p["created_at"],
                        "url": p["web_url"],
                    }
                    for p in resp.json()
                ],
                indent=2,
            )

    except ImportError:

        @mcp.tool()
        @demo_tool("GitLab")
        def gl_get_pipeline(project: str, pipeline_id: int) -> str:  # type: ignore[misc]
            """Get a GitLab CI pipeline. (demo mode, requests not installed)"""
            audit("gl_get_pipeline", {"project": project, "pipeline_id": pipeline_id})
            return json.dumps(
                {
                    "id": pipeline_id,
                    "status": "failed",
                    "ref": "main",
                    "commit": "a1b2c3d4",
                    "duration_seconds": 312,
                    "created_at": "2024-01-15T03:40:00Z",
                    "url": f"https://gitlab.com/{project}/-/pipelines/{pipeline_id}",
                },
                indent=2,
            )

        @mcp.tool()
        @demo_tool("GitLab")
        def gl_list_failed_pipelines(project: str, limit: int = 10) -> str:  # type: ignore[misc]
            """List failed GitLab CI pipelines. (demo mode)"""
            audit("gl_list_failed_pipelines", {"project": project, "limit": limit})
            return json.dumps(
                [
                    {
                        "id": 4242,
                        "ref": "feature/login",
                        "commit": "deadbeef",
                        "created_at": "2024-01-15T03:40:00Z",
                        "url": f"https://gitlab.com/{project}/-/pipelines/4242",
                    }
                ],
                indent=2,
            )
