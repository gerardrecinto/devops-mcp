"""`devops-mcp --check --live`: one read-only call per configured service.

It answers "do these credentials work from this network" before anyone asks
Claude a question. It only reads. It never posts to Slack or Teams and never
prints a secret.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

TIMEOUT = 10


@dataclass
class Result:
    service: str
    status: str  # ok | fail | skipped
    detail: str
    fix: str = ""


def _http(
    service: str,
    method: str,
    url: str,
    fix_creds: str,
    describe: Callable[[Any], str] = lambda r: f"HTTP {r.status_code}",
    **kwargs: Any,
) -> Result:
    host = url.split("/")[2]
    try:
        resp = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.SSLError:
        return Result(service, "fail", f"TLS certificate for {host} is not trusted",
                      "Point REQUESTS_CA_BUNDLE at your organization's CA bundle.")
    except requests.exceptions.RequestException as exc:
        return Result(service, "fail", f"cannot reach {host} ({type(exc).__name__})",
                      "Check outbound access, HTTPS_PROXY and the URL you set.")
    if resp.status_code in (401, 403):
        return Result(service, "fail", f"credentials rejected (HTTP {resp.status_code})", fix_creds)
    if resp.status_code >= 400:
        return Result(service, "fail", f"{host} answered HTTP {resp.status_code}",
                      "Check the URL you set and that the token has read access.")
    try:
        return Result(service, "ok", describe(resp))
    except Exception as exc:  # noqa: BLE001
        return Result(service, "fail", f"{host} answered, but not with the expected reply ({type(exc).__name__})",
                      "Check that the URL points at the service's API, not a login page.")


def _missing(service: str, names: list[str]) -> Result | None:
    gone = [n for n in names if not os.getenv(n)]
    if gone:
        return Result(service, "fail", f"{', '.join(gone)} not set", f"Set {', '.join(gone)} in ~/.devops-mcp/.env and run the check again.")
    return None


def _github() -> Result:
    return _http(
        "github_actions", "GET", "https://api.github.com/user",
        "Check GITHUB_TOKEN: it may be expired, or lack access to your organization (SSO authorization).",
        lambda r: f"authenticated as {r.json()['login']}",
        headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github+json"},
    )


def _gitlab() -> Result:
    base = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
    return _http(
        "gitlab", "GET", f"{base}/api/v4/user", "Check GITLAB_TOKEN and that it has the read_api scope.",
        lambda r: f"authenticated as {r.json()['username']}",
        headers={"PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN", "")},
    )


def _jenkins() -> Result:
    if (m := _missing("jenkins", ["JENKINS_URL", "JENKINS_USER", "JENKINS_TOKEN"])):
        return m
    url = os.environ["JENKINS_URL"].rstrip("/") + "/api/json?tree=mode"
    return _http(
        "jenkins", "GET", url, "Check JENKINS_USER and JENKINS_TOKEN (use an API token, not a password).",
        lambda r: f"reachable, mode {r.json()['mode']}",
        auth=(os.environ["JENKINS_USER"], os.environ["JENKINS_TOKEN"]),
    )


def _servicenow() -> Result:
    if (m := _missing("servicenow", ["SNOW_INSTANCE", "SNOW_USER", "SNOW_PASSWORD"])):
        return m
    return _http(
        "servicenow", "GET", f"https://{os.environ['SNOW_INSTANCE']}/api/now/table/incident?sysparm_limit=1",
        "Check SNOW_USER and SNOW_PASSWORD, and that the account can read the incident table.",
        lambda r: f"incident table readable ({len(r.json()['result'])} row fetched)",
        auth=(os.environ["SNOW_USER"], os.environ["SNOW_PASSWORD"]),
    )


def _slack() -> Result:
    def check(r: Any) -> str:
        body = r.json()
        if not body.get("ok"):
            raise ValueError(body.get("error", "not ok"))
        return f"authenticated as {body.get('user', 'bot')} in {body.get('team', 'workspace')}"

    res = _http(
        "slack", "POST", "https://slack.com/api/auth.test", "Check SLACK_BOT_TOKEN (it starts with xoxb-).", check,
        headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN', '')}"},
    )
    if res.status == "fail" and "expected reply" in res.detail:
        res.detail = "Slack rejected the token"
        res.fix = "Check SLACK_BOT_TOKEN: it may be revoked or from another workspace."
    return res


def _aws() -> Result:
    try:
        import boto3
        from botocore.config import Config

        ident = boto3.client(
            "sts", region_name=os.getenv("AWS_REGION") or None,
            config=Config(connect_timeout=5, read_timeout=TIMEOUT, retries={"max_attempts": 0}),
        ).get_caller_identity()
        return Result("aws", "ok", f"caller {ident['Arn']}")
    except Exception as exc:  # noqa: BLE001
        return Result("aws", "fail", f"{type(exc).__name__}",
                      "Check AWS_PROFILE or the access key variables, that the session has not expired, and outbound access to sts.amazonaws.com.")


def _kubernetes() -> Result:
    try:
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        v = client.VersionApi().get_code(_request_timeout=TIMEOUT)
        return Result("kubernetes", "ok", f"API server {v.git_version}")
    except Exception as exc:  # noqa: BLE001
        return Result("kubernetes", "fail", f"{type(exc).__name__}",
                      "Check KUBECONFIG and the current context (kubectl config current-context), and that the cluster is reachable from here.")


_PROBES: dict[str, Callable[[], Result]] = {
    "kubernetes": _kubernetes,
    "jenkins": _jenkins,
    "github_actions": _github,
    "gitlab": _gitlab,
    "aws": _aws,
    "servicenow": _servicenow,
    "slack": _slack,
}
_NO_PROBE = {
    "azure": "no live probe yet",
    "gcp": "no live probe yet",
    "teams": "not probed: the only call is a message post, and the check never posts",
}


def run_live(configured: list[str]) -> list[Result]:
    out: list[Result] = []
    for name in configured:
        probe = _PROBES.get(name)
        out.append(probe() if probe else Result(name, "skipped", _NO_PROBE.get(name, "no live probe")))
    return out


def report(results: list[Result]) -> tuple[list[str], int]:
    lines = []
    for r in results:
        lines.append(f"  {r.status.upper():<7} {r.service:<15} {r.detail}")
        if r.fix and r.status == "fail":
            lines.append(f"          fix: {r.fix}")
    failed = sum(r.status == "fail" for r in results)
    ok = sum(r.status == "ok" for r in results)
    lines.append(f"{ok} of {len(results)} configured services answered; {failed} failed.")
    return lines, 1 if failed else 0
