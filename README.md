# devops-mcp

> Ask Claude "Why is production down?" — get a real answer, from your live systems.

A production-grade [MCP](https://modelcontextprotocol.io) server that connects Claude to your DevOps stack in real time. Query Kubernetes pods, Jenkins and GitHub Actions builds, and AWS CloudWatch — all in plain English, no context-switching required.

---

## Demo

```
You: "The API deployment has been stuck for 20 minutes. What's going on?"

Claude: I'll check the deployment status and scan for failing pods.

[k8s_get_deployment_status("api-server", "production")]
→ desired: 3  ready: 1  updated: 3  strategy: RollingUpdate
→ Condition: Progressing — ReplicaSetUpdated

[k8s_get_failing_pods("production")]
→ api-server-7d9f8b-xk2p9  CrashLoopBackOff  restarts: 14  node: node-1
→ api-server-4k8m3-rz9q1   CrashLoopBackOff  restarts: 11  node: node-2

[k8s_pod_logs("api-server-7d9f8b-xk2p9", tail_lines=30)]
→ [09:10:03] ERROR  postgresql://db-prod:5432 — Connection refused
→ [09:10:03] FATAL  Could not initialize connection pool. Exiting.

[k8s_get_events("production", event_type="Warning")]
→ OOMKilling  Pod/db-prod-0  "Memory limit exceeded"  count: 3  09:09:47

Root cause: db-prod-0 was OOMKilled at 09:09:47. The two API pods
are crash-looping because the database stopped accepting connections.

Recommended next steps:
  kubectl describe pod db-prod-0 -n production  # check memory stats
  kubectl logs db-prod-0 -n production          # confirm OOM in db logs
  Raise db-prod memory limit: 512Mi → 1Gi
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Claude (LLM)                             │
│   "Why is production down?" / "Why did build #847 fail?"         │
└─────────────────────────┬────────────────────────────────────────┘
                          │  MCP Protocol (stdio)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                      devops-mcp server                           │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │   Kubernetes     │  │ Jenkins / GitHub  │  │     AWS       │  │
│  │                  │  │   Actions         │  │               │  │
│  │ • failing pods   │  │ • build status    │  │ • CW logs     │  │
│  │ • pod logs       │  │ • build logs      │  │ • CW metrics  │  │
│  │ • events         │  │ • failing jobs    │  │ • S3 buckets  │  │
│  │ • deployments    │  │ • run history     │  │ • ECS tasks   │  │
│  └────────┬─────────┘  └────────┬──────────┘  └──────┬────────┘  │
│           └────────────────────┴─────────────────────┘           │
│                          Audit log                               │
│                     ~/.devops-mcp/audit.log                      │
└──────────────────────────────────────────────────────────────────┘
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

---

## Quick start

### Install

```bash
git clone https://github.com/gerardrecinto/devops-mcp.git
cd devops-mcp
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Fill in credentials for each service. Any service without credentials is skipped gracefully.
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
        "AWS_REGION": "us-west-2"
      }
    }
  }
}
```

Restart Claude Desktop. The devops-mcp tools appear in the toolbar.

### Claude API (programmatic)

```python
import subprocess
from anthropic import Anthropic

client = Anthropic()

# Start the MCP server as a subprocess and pass it to the Anthropic client
# See docs: https://docs.anthropic.com/en/docs/agents-and-tools/mcp
```

### Docker

```bash
cp .env.example .env   # fill in credentials
docker-compose up -d
```

---

## Security

All tools are **read-only**. Claude can observe and explain — it cannot modify infrastructure.

| Action | Available |
|---|---|
| Read pod logs, events, deployment status | ✅ |
| Read Jenkins / GitHub Actions build logs | ✅ |
| Read CloudWatch logs and metrics | ✅ |
| `kubectl apply` / trigger builds / modify resources | ❌ |
| AWS resource creation or deletion | ❌ |

**Credentials** are injected via environment variables — never hardcoded. Each integration is independently optional; missing credentials skip that tool group gracefully.

**Audit log**: every tool call is appended to `~/.devops-mcp/audit.log` with ISO timestamp, tool name, and parameters.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=devops_mcp --cov-report=term-missing
```

```
tests/test_kubernetes.py::test_healthy_cluster_returns_message PASSED
tests/test_kubernetes.py::test_crashloop_pod_is_included PASSED
tests/test_kubernetes.py::test_pod_logs_returns_content PASSED
tests/test_kubernetes.py::test_describe_pod_is_valid_json PASSED
tests/test_kubernetes.py::test_demo_mode_on_import_error PASSED
tests/test_jenkins.py::test_successful_build_result PASSED
tests/test_jenkins.py::test_failed_build_result PASSED
tests/test_jenkins.py::test_list_failing_jobs_filters_correctly PASSED
tests/test_aws.py::test_cloudwatch_returns_events PASSED
tests/test_aws.py::test_cloudwatch_empty_returns_message PASSED
tests/test_aws.py::test_metric_returns_datapoints PASSED

11 passed in 0.34s
Coverage: 89%
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
