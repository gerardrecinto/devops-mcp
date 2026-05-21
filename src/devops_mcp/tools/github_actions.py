from __future__ import annotations

import json
import os
from typing import Any, Callable

_GH_API = "https://api.github.com"


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        import requests  # type: ignore

        def _headers() -> dict[str, str]:
            token = os.getenv("GITHUB_TOKEN", "")
            h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
            if token:
                h["Authorization"] = f"Bearer {token}"
            return h

        @mcp.tool()
        def gh_get_workflow_run(owner: str, repo: str, run_id: int) -> str:
            """Get details of a specific GitHub Actions workflow run."""
            audit("gh_get_workflow_run", {"owner": owner, "repo": repo, "run_id": run_id})
            resp = requests.get(
                f"{_GH_API}/repos/{owner}/{repo}/actions/runs/{run_id}",
                headers=_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(
                {
                    "id": data["id"],
                    "name": data["name"],
                    "status": data["status"],
                    "conclusion": data["conclusion"],
                    "branch": data["head_branch"],
                    "commit": data["head_sha"][:8],
                    "created_at": data["created_at"],
                    "url": data["html_url"],
                },
                indent=2,
            )

        @mcp.tool()
        def gh_list_failed_runs(owner: str, repo: str, workflow_id: str = "", limit: int = 10) -> str:
            """List recent failed workflow runs for a repository."""
            audit("gh_list_failed_runs", {"owner": owner, "repo": repo, "workflow_id": workflow_id})
            base = (
                f"{_GH_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
                if workflow_id
                else f"{_GH_API}/repos/{owner}/{repo}/actions/runs"
            )
            resp = requests.get(
                base,
                headers=_headers(),
                params={"status": "failure", "per_page": limit},
                timeout=10,
            )
            resp.raise_for_status()
            runs = resp.json().get("workflow_runs", [])
            return json.dumps(
                [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "branch": r["head_branch"],
                        "commit": r["head_sha"][:8],
                        "created_at": r["created_at"],
                        "url": r["html_url"],
                    }
                    for r in runs
                ],
                indent=2,
            )

    except ImportError:

        @mcp.tool()
        def gh_get_workflow_run(owner: str, repo: str, run_id: int) -> str:  # type: ignore[misc]
            """Get GitHub Actions workflow run details. (demo mode — requests not installed)"""
            audit("gh_get_workflow_run", {"owner": owner, "repo": repo, "run_id": run_id})
            return json.dumps(
                {
                    "id": run_id,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "failure",
                    "branch": "main",
                    "commit": "a1b2c3d4",
                    "created_at": "2024-01-15T03:40:00Z",
                    "url": f"https://github.com/{owner}/{repo}/actions/runs/{run_id}",
                },
                indent=2,
            )

        @mcp.tool()
        def gh_list_failed_runs(owner: str, repo: str, workflow_id: str = "", limit: int = 10) -> str:  # type: ignore[misc]
            """List failed GitHub Actions runs. (demo mode)"""
            audit("gh_list_failed_runs", {"owner": owner, "repo": repo, "workflow_id": workflow_id})
            return json.dumps(
                [
                    {
                        "id": 9876543210,
                        "name": "CI",
                        "branch": "feature/new-endpoint",
                        "commit": "deadbeef",
                        "created_at": "2024-01-15T03:40:00Z",
                        "url": f"https://github.com/{owner}/{repo}/actions/runs/9876543210",
                    }
                ],
                indent=2,
            )
