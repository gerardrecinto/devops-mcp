from __future__ import annotations

import json
import os
from collections import deque
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from devops_mcp.demo import demo_response

_MAX_TAIL_LINES = 1000
_MAX_LINE_CHARS = 2000


def _client() -> tuple[str, tuple[str, str]] | tuple[None, None]:
    url = os.getenv("JENKINS_URL", "").rstrip("/")
    user = os.getenv("JENKINS_USER", "")
    token = os.getenv("JENKINS_TOKEN", "")
    if not (url and user and token):
        return None, None
    return url, (user, token)


def _job_path(job_name: str) -> str:
    """Build the URL path for a job; "folder/job" becomes /job/folder/job/job, names are quoted."""
    parts = [p for p in job_name.strip("/").split("/") if p]
    return "".join(f"/job/{quote(p, safe='')}" for p in parts)


def _friendly_error(exc: Exception, what: str) -> str:
    """Turn a requests failure into a one-line message an assistant can relay."""
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if code == 401 or code == 403:
        return f"Jenkins rejected the credentials while fetching {what} (HTTP {code}). Check JENKINS_USER and JENKINS_TOKEN."
    if code == 404:
        return f"Jenkins could not find {what} (HTTP 404). Check the job name (use folder/job for folder jobs) and build number."
    if code:
        return f"Jenkins returned HTTP {code} while fetching {what}."
    return f"Could not reach Jenkins while fetching {what}: {exc}"


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
            audit(
                "jenkins_get_build_status",
                {"job_name": job_name, "build_number": build_number},
            )
            url, auth = _client()
            if url is None:
                return demo_response(
                    "Jenkins", _demo_build_status(job_name, build_number)
                )
            ref = "lastCompletedBuild" if build_number == 0 else str(build_number)
            try:
                resp = requests.get(
                    f"{url}{_job_path(job_name)}/{ref}/api/json",
                    auth=HTTPBasicAuth(*auth),
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                return _friendly_error(exc, f"build status for {job_name}")
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
        def jenkins_get_build_log(
            job_name: str, build_number: int = 0, tail_lines: int = 50
        ) -> str:
            """Fetch console log for a Jenkins build."""
            audit(
                "jenkins_get_build_log",
                {"job_name": job_name, "build_number": build_number},
            )
            url, auth = _client()
            if url is None:
                return demo_response("Jenkins", _demo_build_log(job_name))
            ref = "lastCompletedBuild" if build_number == 0 else str(build_number)
            try:
                resp = requests.get(
                    f"{url}{_job_path(job_name)}/{ref}/consoleText",
                    auth=HTTPBasicAuth(*auth),
                    timeout=30,
                    stream=True,
                )
                resp.raise_for_status()
                # Console logs can run to hundreds of MB; keep only the tail.
                tail: deque[str] = deque(
                    maxlen=min(max(tail_lines, 1), _MAX_TAIL_LINES)
                )
                for line in resp.iter_lines(decode_unicode=True):
                    tail.append(line[:_MAX_LINE_CHARS])
                resp.close()
            except requests.RequestException as exc:
                return _friendly_error(exc, f"the console log for {job_name}")
            return "\n".join(tail)

        @mcp.tool()
        def jenkins_list_failing_jobs(view: str = "All") -> str:
            """List all jobs currently in a failed state."""
            audit("jenkins_list_failing_jobs", {"view": view})
            url, auth = _client()
            if url is None:
                return demo_response("Jenkins", _demo_failing_jobs())
            try:
                resp = requests.get(
                    f"{url}/view/{quote(view, safe='')}/api/json?tree=jobs[name,color,url]",
                    auth=HTTPBasicAuth(*auth),
                    timeout=10,
                )
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
            except requests.RequestException as exc:
                return _friendly_error(exc, f"jobs in view {view}")
            failing = [
                {"name": j["name"], "url": j["url"]}
                for j in jobs
                if j.get("color", "") in ("red", "red_anime")
            ]
            return json.dumps(failing, indent=2)

    except ImportError:

        @mcp.tool()
        def jenkins_get_build_status(job_name: str, build_number: int = 0) -> str:  # type: ignore[misc]
            """Get Jenkins build status. (demo mode, requests not installed)"""
            audit(
                "jenkins_get_build_status",
                {"job_name": job_name, "build_number": build_number},
            )
            return demo_response("Jenkins", _demo_build_status(job_name, build_number))

        @mcp.tool()
        def jenkins_get_build_log(job_name: str, build_number: int = 0, tail_lines: int = 50) -> str:  # type: ignore[misc]
            """Fetch Jenkins console log. (demo mode)"""
            audit(
                "jenkins_get_build_log",
                {"job_name": job_name, "build_number": build_number},
            )
            return demo_response("Jenkins", _demo_build_log(job_name))

        @mcp.tool()
        def jenkins_list_failing_jobs(view: str = "All") -> str:  # type: ignore[misc]
            """List failing Jenkins jobs. (demo mode)"""
            audit("jenkins_list_failing_jobs", {"view": view})
            return demo_response("Jenkins", _demo_failing_jobs())


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
        "[Pipeline] Start of Pipeline\n"
        "[Pipeline] stage (Build)\n"
        "[backend-deploy] Running shell script\n"
        "+ docker build -t myapp/backend:latest .\n"
        "Step 1/8 : FROM python:3.12-slim\n"
        "ERROR: failed to solve: python:3.12-slim: not found\n"
        "[Pipeline] End of Pipeline\n"
        "Finished: FAILURE\n"
    )


def _demo_failing_jobs() -> list[dict[str, Any]]:
    return [
        {
            "name": "backend-deploy",
            "url": "http://jenkins.example.com/job/backend-deploy/",
        },
        {
            "name": "integration-tests",
            "url": "http://jenkins.example.com/job/integration-tests/",
        },
    ]
