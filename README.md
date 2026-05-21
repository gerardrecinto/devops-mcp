# devops-mcp

> Ask Claude "Why is production down?" and get a real answer from your live systems.

An [MCP](https://modelcontextprotocol.io) server that connects Claude to your DevOps stack. Query Kubernetes, Jenkins, GitHub Actions, AWS, Azure, GCP, ServiceNow, Slack, and Microsoft Teams in plain English without switching between tabs and terminals.

---

## Demo

```
You: "The API deployment has been stuck for 20 minutes. What's going on?"

Claude: I'll check the deployment status and scan for failing pods.

[k8s_get_deployment_status("api-server", "production")]
-> desired: 3  ready: 1  updated: 3  strategy: RollingUpdate
-> Condition: Progressing - ReplicaSetUpdated

[k8s_get_failing_pods("production")]
-> api-server-7d9f8b-xk2p9  CrashLoopBackOff  restarts: 14  node: node-1
-> api-server-4k8m3-rz9q1   CrashLoopBackOff  restarts: 11  node: node-2

[k8s_pod_logs("api-server-7d9f8b-xk2p9", tail_lines=30)]
-> [09:10:03] ERROR  postgresql://db-prod:5432: Connection refused
-> [09:10:03] FATAL  Could not initialize connection pool. Exiting.

[k8s_get_events("production", event_type="Warning")]
-> OOMKilling  Pod/db-prod-0  "Memory limit exceeded"  count: 3  09:09:47

[snow_get_incident("INC0045231")]
-> short_description: API gateway 502 errors spiking
-> state: In Progress  assigned_to: oncall-sre

Root cause: db-prod-0 was OOMKilled at 09:09:47. The two API pods are
crash-looping because the database stopped accepting connections.
INC0045231 is already open and assigned to oncall-sre.

Recommended next steps:
  kubectl describe pod db-prod-0 -n production  # check memory stats
  kubectl logs db-prod-0 -n production          # confirm OOM in db logs
  Raise db-prod memory limit: 512Mi -> 1Gi
```

---

## Architecture

```
+---------------------------------------------------------------------------------+
|                              Claude (LLM)                                       |
|   "Why is production down?" / "Which incidents are open right now?"             |
+----------------------------------+----------------------------------------------+
                                   |  MCP Protocol (stdio)
                                   v
+---------------------------------------------------------------------------------+
|                           devops-mcp server                                     |
|                                                                                 |
|  +-------------+  +-------------+  +-------------+  +-------------+            |
|  | Kubernetes  |  | Jenkins/GHA |  |    AWS      |  |    Azure    |            |
|  | pods/logs   |  | build status|  | CW logs     |  | Monitor     |            |
|  | events      |  | build logs  |  | metrics     |  | AKS status  |            |
|  | rollouts    |  | failing jobs|  | S3 / ECS    |  | res. health |            |
|  +-------------+  +-------------+  +-------------+  +-------------+            |
|                                                                                 |
|  +-------------+  +-------------+  +-------------+  +-------------+            |
|  |    GCP      |  | ServiceNow  |  |    Slack    |  |   Teams     |            |
|  | Cloud Log   |  | incidents   |  | post alerts |  | post alerts |            |
|  | Monitoring  |  | changes     |  | history     |  | messages    |            |
|  | GKE / Run   |  |             |  | search      |  | channels    |            |
|  +-------------+  +-------------+  +-------------+  +-------------+            |
|                                                                                 |
|                      Audit log  (~/.devops-mcp/audit.log)                      |
+---------------------------------------------------------------------------------+
```

---

## Available tools

### Kubernetes
| Tool | What it answers |
|---|---|
| `k8s_get_failing_pods` | What pods are crashing right now? |
| `k8s_pod_logs` | What is this pod printing to stdout/stderr? |
| `k8s_describe_pod` | Full state: conditions, restart counts, recent events |
| `k8s_get_events` | What Warning events has the cluster emitted recently? |
| `k8s_get_deployment_status` | Is this rollout progressing or stuck? |

### Jenkins
| Tool | What it answers |
|---|---|
| `jenkins_get_build_status` | Did build #N succeed or fail, and how long did it take? |
| `jenkins_get_build_log` | What did the last N lines of the build print? |
| `jenkins_list_failing_jobs` | Which jobs are currently red? |

### GitHub Actions
| Tool | What it answers |
|---|---|
| `gh_get_workflow_run` | Status and conclusion for a specific run |
| `gh_list_failed_runs` | Which workflows have failed in the last 24 hours? |

### AWS
| Tool | What it answers |
|---|---|
| `aws_get_cloudwatch_logs` | What did this log group emit matching this filter? |
| `aws_get_metric` | What does this CloudWatch metric look like right now? |
| `aws_describe_s3_bucket` | Versioning, lifecycle rules, encryption config |
| `aws_get_ecs_service_status` | Running vs desired vs pending task counts |

### Azure
| Tool | What it answers |
|---|---|
| `azure_get_monitor_logs` | Run a KQL query against a Log Analytics workspace |
| `azure_get_metric` | What does this Azure Monitor metric look like right now? |
| `azure_get_aks_node_status` | AKS agent pool provisioning state and node counts |
| `azure_get_resource_health` | Is this Azure resource healthy? |

### GCP
| Tool | What it answers |
|---|---|
| `gcp_get_logs` | Query Cloud Logging with a filter expression |
| `gcp_get_metric` | What does this Cloud Monitoring metric look like? |
| `gcp_get_gke_cluster_status` | GKE cluster and node pool status |
| `gcp_get_cloud_run_status` | Cloud Run revision status and traffic split |

### ServiceNow
| Tool | What it answers |
|---|---|
| `snow_list_incidents` | What incidents are open right now? |
| `snow_get_incident` | Full detail on a specific incident (INC0012345) |
| `snow_get_change_requests` | What changes are scheduled or in flight? |

### Slack
| Tool | What it does |
|---|---|
| `slack_post_message` | Post an alert or notification to a channel |
| `slack_get_channel_history` | What was said in #incidents in the last hour? |
| `slack_search_messages` | When was this topic last discussed across Slack? |

### Microsoft Teams
| Tool | What it does |
|---|---|
| `teams_post_message` | Post an alert card to a channel via webhook |
| `teams_get_channel_messages` | What was said in this channel recently? |
| `teams_list_channels` | What channels exist in this team? |

---

## Quick start

### Install

```bash
git clone https://github.com/gerardrecinto/devops-mcp.git
cd devops-mcp
pip install -e .

# Optional extras for the integrations you use
pip install -e ".[azure]"   # Azure Monitor + AKS
pip install -e ".[gcp]"     # Cloud Logging + Monitoring + GKE + Cloud Run
pip install -e ".[slack]"   # Slack SDK
# ServiceNow and Teams use requests, which is already included
```

### Configure

```bash
cp .env.example .env
# Fill in credentials for each service. Any service without credentials is skipped.
```

### Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "devops-mcp": {
      "command": "devops-mcp",
      "env": {
        "KUBECONFIG": "/Users/you/.kube/config",
        "JENKINS_URL": "https://jenkins.example.com",
        "JENKINS_USER": "your-user",
        "JENKINS_TOKEN": "your-api-token",
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx",
        "AWS_REGION": "us-west-2",
        "AZURE_TENANT_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "AZURE_CLIENT_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "AZURE_CLIENT_SECRET": "your-client-secret",
        "AZURE_SUBSCRIPTION_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "GCP_PROJECT_ID": "my-project-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/you/.gcp/service-account.json",
        "SNOW_INSTANCE": "yourcompany.service-now.com",
        "SNOW_USER": "your-user",
        "SNOW_PASSWORD": "your-password",
        "SLACK_BOT_TOKEN": "xoxb-xxxxxxxxxxxxxxxxxxxx",
        "TEAMS_WEBHOOK_URL": "https://outlook.office.com/webhook/xxxx",
        "TEAMS_TENANT_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "TEAMS_CLIENT_ID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "TEAMS_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

Restart Claude Desktop. The devops-mcp tools appear in the toolbar.

### Docker

```bash
cp .env.example .env   # fill in credentials
docker-compose up -d
```

---

## Security

Infrastructure tools (Kubernetes, AWS, Azure, GCP, Jenkins, GitHub Actions) are **read-only**. Claude can observe and explain but cannot modify infrastructure. Slack and Teams tools can post messages for incident alerting.

| Action | Available |
|---|---|
| Read pod logs, events, deployment status | yes |
| Read build logs and pipeline status | yes |
| Read CloudWatch / Azure Monitor / Cloud Logging | yes |
| Read ServiceNow incidents and change requests | yes |
| Post to Slack channels | yes |
| Post to Teams channels via webhook | yes |
| `kubectl apply` / trigger builds / modify resources | no |
| AWS / Azure / GCP resource creation or deletion | no |
| Create or close ServiceNow records | no |

**Credentials** are injected via environment variables, never hardcoded. Each integration is independently optional; missing credentials skip that tool group.

**Audit log**: every tool call is appended to `~/.devops-mcp/audit.log` with ISO timestamp, tool name, and parameters.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=devops_mcp --cov-report=term-missing
```

```
tests/test_azure.py::test_monitor_logs_demo_returns_events PASSED
tests/test_azure.py::test_get_metric_demo_returns_datapoints PASSED
tests/test_azure.py::test_aks_node_status_demo_returns_pools PASSED
tests/test_azure.py::test_resource_health_demo_returns_available PASSED
tests/test_gcp.py::test_get_logs_demo_returns_entries PASSED
tests/test_gcp.py::test_get_metric_demo_returns_points PASSED
tests/test_gcp.py::test_gke_status_demo_returns_running PASSED
tests/test_gcp.py::test_cloud_run_demo_returns_uri PASSED
tests/test_kubernetes.py::test_healthy_cluster_returns_message PASSED
tests/test_kubernetes.py::test_crashloop_pod_is_included PASSED
tests/test_kubernetes.py::test_pod_logs_returns_content PASSED
tests/test_kubernetes.py::test_describe_pod_is_valid_json PASSED
tests/test_kubernetes.py::test_demo_mode_on_import_error PASSED
tests/test_jenkins.py::test_successful_build_result PASSED
tests/test_jenkins.py::test_failed_build_result PASSED
tests/test_jenkins.py::test_list_failing_jobs_filters_correctly PASSED
tests/test_aws.py::test_cloudwatch_logs_demo_returns_events PASSED
tests/test_aws.py::test_get_metric_demo_returns_datapoints PASSED
tests/test_aws.py::test_ecs_service_status_demo_shows_degraded PASSED
tests/test_servicenow.py::test_list_incidents_demo_returns_incidents PASSED
tests/test_servicenow.py::test_get_incident_demo_returns_details PASSED
tests/test_servicenow.py::test_get_change_requests_demo_returns_changes PASSED
tests/test_slack.py::test_post_message_demo_returns_ok PASSED
tests/test_slack.py::test_get_channel_history_demo_returns_messages PASSED
tests/test_slack.py::test_search_messages_demo_returns_matches PASSED
tests/test_teams.py::test_post_message_demo_returns_ok PASSED
tests/test_teams.py::test_get_channel_messages_demo_returns_messages PASSED
tests/test_teams.py::test_list_channels_demo_returns_channels PASSED

28 passed in 0.52s
Coverage: 91%
```

---

## Roadmap

- [ ] Grafana alert history
- [ ] PagerDuty incident lookup
- [ ] Terraform state drift detection
- [ ] Datadog APM trace summaries
- [ ] ArgoCD sync status
- [ ] SSE transport (for web-based MCP clients)

---

## Contributing

PRs welcome. Open an issue first for significant new integrations.

---

## License

MIT
