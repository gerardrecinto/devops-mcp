from __future__ import annotations

import json
import os
from typing import Any, Callable


def _client() -> tuple[str, tuple[str, str]] | tuple[None, None]:
    url = os.getenv("JENKINS_URL", "").rstrip("/")
    user = os.getenv("JENKINS_USER", "")
    token = os.getenv("JENKINS_TOKEN", "")
    if not (url and user and token):
        return None, None
    return url, (user, token)


def register(mcp: Any, audit: Callable[[str, dict], None]) -> None:
    try:
        import requests  # type: ignore
        from requests.auth import HTTPBasicAuth  # type: ignore

        @mcp.tool()
        def jenkins_get_build_status(job_name: str, build_number: int = 0) -> str:
            """
            Get status of a Jenkins build.
            build_number=0 fetches the last completed build.
            """
            audit("jenkins_get_build_status", {"job_name": job_name, "build_number": build_number})
            url, auth = _client()
            if url is None:
                return json.dumps(_demo_build_status(job_name, build_number))
            ref = "lastCompletedBuild" if build_number == 0 else str(build_number)
            resp = requests.get(
                f"{url}/job/{job_name}/{ref}/api/json",
                auth=HTTPBasicAuth(*auth),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(
                {
                    "job": job_name,
                    "build": data.get("number"),
                    "result": data.get("result"),
                    "duration_s": round(data.get("duration", 0) / 1000),
                    "url": data.get("url"),
                    "timestamp": data.get("timestamp"),
                },
                indent=2,
            )

        @mcp.tool()
        def jenkins_get_build_log(job_name: str, build_number: int = 0, tail_lines: int = 50) -> str:
            """Fetch console log for a Jenkins build."""
            audit("jenkins_get_build_log", {"job_name": job_name, "build_number": build_number})
            url, auth = _client()
            if url is None:
                return _demo_build_log(job_name)
            ref = "lastCompletedBuild" if build_number == 0 else str(build_number)
            resp = requests.get(
                f"{url}/job/{job_name}/{ref}/consoleText",
                auth=HTTPBasicAuth(*auth),
                timeout=30,
            )
            resp.raise_for_status()
            lines = resp.text.splitlines()
            return "\n".join(lines[-tail_lines:])

        @mcp.tool()
        def jenkins_list_failing_jobs(view: str = "All") -> str:
            """List all jobs currently in a failed state."""
            audit("jenkins_list_failing_jobs", {"view": view})
            url, auth = _client()
            if url is None:
                return json.dumps(_demo_failing_jobs(), indent=2)
            resp = requests.get(
                f"{url}/view/{view}/api/json?tree=jobs[name,color,url]",
                auth=HTTPBasicAuth(*auth),
                timeout=10,
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
            failing = [
                {"name": j["name"], "url": j["url"]}
                for j in jobs
                if j.get("color", "") == "red"
            ]
            return json.dumps(failing, indent=2)

    except ImportError:

        @mcp.tool()
        def jenkins_get_build_status(job_name: str, build_number: int = 0) -> str:  # type: ignore[misc]
            """Get Jenkins build status. (demo mode — requests not installed)"""
            audit("jenkins_get_build_status", {"job_name": job_name, "build_number": build_number})
            return json.dumps(_demo_build_status(job_name, build_number), indent=2)

        @mcp.tool()
        def jenkins_get_build_log(job_name: str, build_number: int = 0, tail_lines: int = 50) -> str:  # type: ignore[misc]
            """Fetch Jenkins console log. (demo mode)"""
            audit("jenkins_get_build_log", {"job_name": job_name, "build_number": build_number})
            return _demo_build_log(job_name)

        @mcp.tool()
        def jenkins_list_failing_jobs(view: str = "All") -> str:  # type: ignore[misc]
            """List failing Jenkins jobs. (demo mode)"""
            audit("jenkins_list_failing_jobs", {"view": view})
            return json.dumps(_demo_failing_jobs(), indent=2)


def _demo_build_status(job_name: str, build_number: int) -> dict[str, Any]:
    return {
        "job": job_name,
        "build": build_number or 42,
        "result": "FAILURE",
        "duration_s": 187,
        "url": "http://jenkins.example.com/job/backend-deploy/42/",
        "timestamp": 1705305600000,
    }


def _demo_build_log(job_name: str) -> str:
    return (
        f"[Pipeline] Start of Pipeline\n"
        f"[Pipeline] stage (Build)\n"
        f"[backend-deploy] Running shell script\n"
        f"+ docker build -t myapp/backend:latest .\n"
        f"Step 1/8 : FROM python:3.12-slim\n"
        f"ERROR: failed to solve: python:3.12-slim: not found\n"
        f"[Pipeline] End of Pipeline\n"
        f"Finished: FAILURE\n"
    )


def _demo_failing_jobs() -> list[dict[str, Any]]:
    return [
        {"name": "backend-deploy", "url": "http://jenkins.example.com/job/backend-deploy/"},
        {"name": "integration-tests", "url": "http://jenkins.example.com/job/integration-tests/"},
    ]
