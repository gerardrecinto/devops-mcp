# devops-mcp

![CI](https://github.com/gerardrecinto/devops-mcp/actions/workflows/ci.yml/badge.svg) ![License](https://img.shields.io/badge/License-MIT-lightgrey)

devops-mcp lets Claude read from your Kubernetes, Jenkins, GitHub Actions, AWS, Azure, GCP, ServiceNow, Slack and Teams, so on-call engineers can ask one question instead of checking six dashboards.

New here? Claude can look at your servers and build systems for you and explain what it finds, but it cannot change them.

It is an MCP server. MCP (Model Context Protocol) is the way Claude Code and Claude Desktop call outside tools. Site with the tool browser: https://gerardrecinto.github.io/devops-mcp/

## Try it in 60 seconds

You need Python 3.11 or later and [pipx](https://pipx.pypa.io).

```bash
pipx install "git+https://github.com/gerardrecinto/devops-mcp.git"
claude mcp add devops-mcp -- devops-mcp
devops-mcp --check
```

`--check` prints what is connected and what to do next. Then ask Claude:

> Which pods are failing in my cluster?

With no other setup it uses your current kubeconfig (`~/.kube/config`), so the answer is about your real cluster. A service you have not set up returns a plain "not configured" error.

This installs from GitHub on purpose. The `devops-mcp` package on PyPI is a different project, and this one is not published there yet.

## Example

Illustrative only. The pod names, incident number and times are made up to show the flow. They are not output from a real system.

```
You: "The API deployment has been stuck for 20 minutes. What's going on?"

Claude:
  [k8s_get_deployment_status("api-server", "production")]
  desired: 3  ready: 1  updated: 3  strategy: RollingUpdate

  [k8s_get_failing_pods("production")]
  api-server-7d9f8b-xk2p9  CrashLoopBackOff  restarts: 14

  [k8s_pod_logs("api-server-7d9f8b-xk2p9", tail_lines=30)]
  [09:10:03] FATAL  postgresql://db-prod:5432: Connection refused

  [k8s_get_events("production", event_type="Warning")]
  OOMKilling  Pod/db-prod-0  "Memory limit exceeded"  count: 3

  Claude: db-prod-0 was OOMKilled, so the API pods cannot reach the database.
```

## Connect more systems

Copy `.env.example` to `~/.devops-mcp/.env` and fill in only the services you use. The server reads that file on start, then restart your client. Run `devops-mcp --check` again to confirm.

Azure, GCP and Slack need extra packages:

```bash
pipx install --force "mcp-devops[azure,gcp,slack] @ git+https://github.com/gerardrecinto/devops-mcp.git"
```

To see the output shape before connecting anything, add the demo flag. Every response is then labelled as sample data and is not real information about your systems. Remove the flag once you connect real systems.

```bash
claude mcp add devops-mcp -e DEVOPS_MCP_DEMO=1 -- devops-mcp
```

## Tools

33 tools. The full list with arguments is in the [tool browser](https://gerardrecinto.github.io/devops-mcp/#tools), and the tables are below.

| Service | Tools |
|---|---|
| Incident timeline | 1 |
| Kubernetes | 5 |
| Jenkins | 3 |
| GitHub Actions | 2 |
| AWS | 4 |
| Azure | 4 |
| GCP | 4 |
| ServiceNow | 3 |
| Slack and Teams | 6 |
| Server health | 1 |

## What it does and does not do

- It is read-only by default. Read-only means no tool applies, deletes, restarts or triggers anything.
- The only writes are Slack and Teams messages, and they are refused unless you set `DEVOPS_MCP_ENABLE_WRITES=1`.
- Every tool call is logged to `~/.devops-mcp/audit.log`, with secret-like values redacted.
- It reports what the APIs return. Claude's explanation of a root cause is a hypothesis to check, not a verdict.
- It does not create or close ServiceNow records, run `kubectl apply`, or start builds.

## More detail

<details>
<summary>Every tool, by service</summary>

#### Incident timeline
| Tool | What it answers |
|---|---|
| `incident_timeline` | What changed, and what broke, in the last N hours? One ordered view across ServiceNow, Kubernetes, GitHub Actions and Jenkins, with the changes that landed just before the first failure listed as suspects |

Suspects are matched by time proximity (a change within 2 hours before the first failure) and the response says so. A source that is unconfigured, in demo mode or failing is reported as skipped and never filled in with sample data.

#### Kubernetes
| Tool | What it answers |
|---|---|
| `k8s_get_failing_pods` | What pods are crashing right now? |
| `k8s_pod_logs` | What is this pod printing? |
| `k8s_describe_pod` | Full state: conditions, restart counts, events |
| `k8s_get_events` | What Warnings has the cluster emitted? |
| `k8s_get_deployment_status` | Is this rollout progressing or stuck? |

#### Jenkins
| Tool | What it answers |
|---|---|
| `jenkins_get_build_status` | Did build #N succeed, and how long did it take? |
| `jenkins_get_build_log` | Last N lines of a build |
| `jenkins_list_failing_jobs` | Which jobs are currently red? |

#### GitHub Actions
| Tool | What it answers |
|---|---|
| `gh_get_workflow_run` | Status and conclusion for a specific run |
| `gh_list_failed_runs` | Which workflows have failed in the last 24 hours? |

#### AWS
| Tool | What it answers |
|---|---|
| `aws_get_cloudwatch_logs` | What did this log group emit? |
| `aws_get_metric` | Current CloudWatch metric value |
| `aws_describe_s3_bucket` | Versioning, lifecycle, encryption config |
| `aws_get_ecs_service_status` | Running vs desired vs pending |

#### Azure
| Tool | What it answers |
|---|---|
| `azure_get_monitor_logs` | KQL query against Log Analytics |
| `azure_get_metric` | Azure Monitor metric |
| `azure_get_aks_node_status` | AKS node pool state |
| `azure_get_resource_health` | Is this Azure resource healthy? |

#### GCP
| Tool | What it answers |
|---|---|
| `gcp_get_logs` | Cloud Logging filter query |
| `gcp_get_metric` | Cloud Monitoring metric |
| `gcp_get_gke_cluster_status` | GKE cluster and node pool status |
| `gcp_get_cloud_run_status` | Cloud Run revision and traffic split |

#### ServiceNow
| Tool | What it answers |
|---|---|
| `snow_list_incidents` | Open incidents right now |
| `snow_get_incident` | Full detail on INC0012345 |
| `snow_get_change_requests` | Scheduled or in-flight changes |

#### Slack / Teams
| Tool | What it does |
|---|---|
| `slack_post_message` | Post to a channel (needs `DEVOPS_MCP_ENABLE_WRITES=1`) |
| `slack_get_channel_history` | What was said in #incidents recently? |
| `slack_search_messages` | Search Slack messages across channels |
| `teams_post_message` | Post an alert card via webhook (needs `DEVOPS_MCP_ENABLE_WRITES=1`) |
| `teams_get_channel_messages` | Recent messages in a Teams channel (Graph API) |
| `teams_list_channels` | Channels in a Teams team (Graph API) |

#### Server
| Tool | What it answers |
|---|---|
| `devops_mcp_health` | Which integrations are configured, and are demo mode and writes on? |

Tool failures come back as `{"error", "message", "hint"}` instead of a stack trace.

</details>

<details>
<summary>Docker</summary>

The image includes every integration. It speaks MCP over stdio, so the client starts it:

```bash
docker pull ghcr.io/gerardrecinto/devops-mcp:latest
claude mcp add devops-mcp -- docker run -i --rm --env-file ~/.devops-mcp/.env \
  -v ~/.kube:/home/devops-mcp/.kube:ro ghcr.io/gerardrecinto/devops-mcp:latest
```

</details>

<details>
<summary>Claude Desktop</summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`, then restart:

```json
{
  "mcpServers": {
    "devops-mcp": {
      "command": "devops-mcp"
    }
  }
}
```

Credentials go in `~/.devops-mcp/.env` (see `.env.example`). To try sample data first, add `"env": { "DEVOPS_MCP_DEMO": "1" }` and remove it later.

</details>

<details>
<summary>Why it is built this way</summary>

A first draft of "wrap the Kubernetes API in an MCP tool" is easy. The parts that make it safe to run against production are not, and each one is tested here:

- **One timeline instead of six dashboards.** `incident_timeline` merges changes, CI failures, cluster warnings and incidents into one ordered view and names the changes that landed shortly before things broke. That cross-system join is the part a single-service wrapper does not give you.
- **It never invents data.** An unconfigured service returns a plain "not configured" error. Sample data is opt-in (`DEVOPS_MCP_DEMO=1`) and every response is labelled, so an assistant cannot report a made-up OOMKill or a Slack message that was never sent.
- **It finds the failures that matter.** A crash-looping pod reports phase `Running`; the reason sits on the container state. The pod check reads container waiting and terminated reasons, so CrashLoopBackOff and ImagePullBackOff are caught, not just `Pending`.
- **Read-only by default.** No tool applies, deletes, restarts or triggers anything. The only writes are Slack and Teams messages, and those are refused unless the operator sets `DEVOPS_MCP_ENABLE_WRITES=1`.
- **Prompt-injection aware.** A webhook URL supplied by the model is ignored unless its host is in `DEVOPS_MCP_TEAMS_WEBHOOK_ALLOWLIST` and is an https Microsoft endpoint, so injected text in a log line cannot make the server POST channel content to an arbitrary host.
- **A private audit trail.** Every tool call is logged as one JSON line in `~/.devops-mcp/audit.log` (mode 0600, rotated at 10 MB). Secret-like parameters are redacted, message tools log the destination and a SHA-256 of the body instead of the body, and a logging failure never breaks a tool.
- **Bounded output.** Pod logs are capped by lines and bytes (a cut is marked `[truncated ...]`), and Jenkins console logs are streamed so a multi-hundred-MB build log cannot exhaust memory.
- **Partial installs work.** Each integration loads on its own; one broken module never stops the rest.

</details>

<details>
<summary>Architecture</summary>

> See [docs/architecture.md](docs/architecture.md) for the full protocol flow, tool registration, and audit logging diagrams.

> See [docs/architecture.md](docs/architecture.md) for the full protocol flow, tool registration, and audit logging diagrams.

```
+-----------------------------------------------------------------------+
|                           Claude (LLM)                                |
|   "Why is production down?" / "Which jobs are failing right now?"     |
+-----------------------------------+-----------------------------------+
                                    |  MCP Protocol (stdio)
                                    v
+-----------------------------------------------------------------------+
|                          devops-mcp server                            |
|                                                                       |
|  Kubernetes  |  Jenkins/GHA  |  AWS           |  Azure               |
|  pods/events |  build logs   |  CW logs       |  Monitor/AKS         |
|  deployment  |  failing jobs |  metrics/ECS   |  resource health     |
|              |               |                |                      |
|  GCP         |  ServiceNow   |  Slack         |  Teams               |
|  Cloud Logs  |  incidents    |  post/search   |  post/messages       |
|  GKE/Run     |  changes      |  history       |  channels            |
|                                                                       |
|              Audit log  (~/.devops-mcp/audit.log)                    |
+-----------------------------------------------------------------------+
```

</details>

<details>
<summary>Partial installs</summary>

Each tool module (Kubernetes, Jenkins, AWS, etc.) loads independently. If a module fails to import, the server logs the error and continues. Every other module still registers its tools normally. The version is logged at startup.

A service without credentials answers with a "not configured" error instead of guessing. Set `DEVOPS_MCP_DEMO=1` to get labelled sample data instead.

</details>

<details>
<summary>Security</summary>

Infrastructure tools are **read-only**. Claude can observe and explain, not modify. The Slack and Teams post tools are the only writes, and they are off until you set `DEVOPS_MCP_ENABLE_WRITES=1`.

| Action | Available |
|---|---|
| Read pod logs, events, deployment status | yes |
| Read build logs and pipeline status | yes |
| Read CloudWatch / Azure Monitor / Cloud Logging | yes |
| Read ServiceNow incidents and changes | yes |
| Post to Slack / Teams | only with `DEVOPS_MCP_ENABLE_WRITES=1` |
| `kubectl apply` / trigger builds / modify resources | no |
| Create or close ServiceNow records | no |

To let the model pick a Teams webhook per call, list the allowed hosts in `DEVOPS_MCP_TEAMS_WEBHOOK_ALLOWLIST` (comma-separated). Otherwise only `TEAMS_WEBHOOK_URL` is used.

Credentials are environment variables only. Each service is independently optional.
Every tool call is appended to `~/.devops-mcp/audit.log` with secret-like parameters redacted.

For the commercial path, launch angles, and first-customer profile, see [docs/go-to-market.md](docs/go-to-market.md).

</details>

<details>
<summary>Run the tests</summary>

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=devops_mcp
```

</details>

<details>
<summary>Roadmap</summary>

- [ ] Grafana alert history
- [ ] PagerDuty incident lookup
- [ ] Terraform state drift detection
- [ ] ArgoCD sync status
- [ ] SSE transport

</details>

For the commercial path and first-customer profile, see [docs/go-to-market.md](docs/go-to-market.md).

## License

MIT
