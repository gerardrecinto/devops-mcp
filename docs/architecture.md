# Architecture: devops-mcp

## Overview

`devops-mcp` is an MCP (Model Context Protocol) server that gives Claude live, read-only access to 9 DevOps tool categories: Kubernetes, Jenkins, GitHub Actions, AWS, Azure, GCP, ServiceNow, Slack, and Microsoft Teams. Claude calls tools on this server the same way it calls any MCP tool — no HTTP wrapper, no separate API layer.

Every tool call is appended to `~/.devops-mcp/audit.log` as a JSON line before the result is returned.

---

## MCP Protocol Flow

```mermaid
sequenceDiagram
    participant User
    participant Claude
    participant MCP Client
    participant devops-mcp Server
    participant Tool Module
    participant External API

    User->>Claude: "What pods are failing?"
    Claude->>MCP Client: tool_call {name: "k8s_get_failing_pods", params: {namespace: "production"}}
    MCP Client->>devops-mcp Server: tool_call request (stdio)
    devops-mcp Server->>Tool Module: kubernetes.k8s_get_failing_pods(params)
    Note over devops-mcp Server: _audit("k8s_get_failing_pods", params) → audit.log
    Tool Module->>External API: kubectl / Kubernetes API query
    External API-->>Tool Module: pod list with status
    Tool Module-->>devops-mcp Server: result
    devops-mcp Server-->>MCP Client: tool_result
    MCP Client-->>Claude: result for reasoning
    Claude-->>User: "Two pods in CrashLoopBackOff: api-server-7d9f8b, api-server-4k8m3"
```

---

## Tool Module Registration

```mermaid
flowchart LR
    main["main()"]
    init["_init_audit()"]
    run["mcp.run()"]

    main --> init
    init --> k8s["kubernetes.register(mcp, _audit)"]
    init --> jen["jenkins.register(mcp, _audit)"]
    init --> gha["github_actions.register(mcp, _audit)"]
    init --> aws["aws.register(mcp, _audit)"]
    init --> az["azure.register(mcp, _audit)"]
    init --> gcp["gcp.register(mcp, _audit)"]
    init --> snow["servicenow.register(mcp, _audit)"]
    init --> sl["slack.register(mcp, _audit)"]
    init --> tm["teams.register(mcp, _audit)"]

    k8s --> run
    jen --> run
    gha --> run
    aws --> run
    az --> run
    gcp --> run
    snow --> run
    sl --> run
    tm --> run
```

Each tool module calls `mcp.tool()` (FastMCP decorator) during `register()` to bind its functions to the server. After all 9 modules register, `mcp.run()` starts the stdio transport loop.

---

## Audit Logging Flow

```mermaid
sequenceDiagram
    participant Tool Handler
    participant _audit
    participant audit.log

    Tool Handler->>_audit: _audit("jenkins_get_build_log", {job: "api", build: 42})
    _audit->>audit.log: append {"ts": "2026-06-01T09:10:03Z", "tool": "jenkins_get_build_log", "params": {...}}
    Note over audit.log: One JSON line per call, never truncated
    Tool Handler->>Tool Handler: execute tool logic
    Tool Handler->>_audit: (optional post-call audit for error/result metadata)
```

Audit entries are written before tool execution. The log is append-only and lives at `~/.devops-mcp/audit.log`. It captures timestamp (UTC ISO-8601), tool name, and all parameters — enough to reconstruct who queried what and when.

---

## Component Diagram

```mermaid
flowchart TD
    claude["Claude (AI)\nClaude Desktop / Claude Code"]
    server["devops-mcp Server\nFastMCP · stdio transport"]
    audit["~/.devops-mcp/audit.log\nappend-only JSON lines"]

    claude -- "MCP Protocol (stdio)" --> server

    server --> k8s_mod["kubernetes module\n5 tools"]
    server --> jen_mod["jenkins module\n3 tools"]
    server --> gha_mod["github_actions module\n2 tools"]
    server --> aws_mod["aws module\n4 tools"]
    server --> az_mod["azure module\n4 tools"]
    server --> gcp_mod["gcp module\n4 tools"]
    server --> snow_mod["servicenow module\n3 tools"]
    server --> sl_mod["slack module\n2 tools"]
    server --> tm_mod["teams module\n1 tool"]
    server --> audit

    k8s_mod --> k8s_api["Kubernetes API"]
    jen_mod --> jenkins_api["Jenkins REST API"]
    gha_mod --> gh_api["GitHub API"]
    aws_mod --> aws_api["AWS (boto3 / CloudWatch)"]
    az_mod --> az_api["Azure Monitor / AKS"]
    gcp_mod --> gcp_api["GCP Logging / Monitoring / GKE"]
    snow_mod --> snow_api["ServiceNow REST API"]
    sl_mod --> slack_api["Slack API (slack-sdk)"]
    tm_mod --> teams_api["Teams Webhook"]
```

---

## Design Decisions

**Why MCP over a REST API?**

> **Interview note:** Claude natively speaks the MCP protocol — it calls `tool_call` messages the same way a function is invoked. Wrapping these tools in a REST API would require a separate HTTP server, auth layer, and client library. MCP eliminates all of that: the server runs as a subprocess over stdio and Claude discovers available tools at startup via `tools/list`.

**Why an audit log?**

> **Interview note:** Every tool call is logged before execution. This satisfies two concerns simultaneously: security (knowing which credentials were exercised and when) and compliance (a tamper-evident append-only record of all queries). It also makes incident post-mortems reproducible — you can replay exactly what Claude queried during an outage.

**Why modular registration (`module.register(mcp, _audit)`)?**

> **Interview note:** This is the Open/Closed Principle in practice. Adding a new integration — say, PagerDuty — means creating one file (`pagerduty.py`) and adding one line (`pagerduty.register(mcp, _audit)`) in `main()`. The server core never changes. Each module owns its own tool definitions, credential checks, and error handling.

**Why FastMCP?**

> **Interview note:** FastMCP is a higher-level wrapper over the base `mcp` SDK. It exposes a `@mcp.tool()` decorator that handles JSON schema generation, input validation, and result serialization automatically. Without it, each tool would require manually constructing `Tool` objects and writing `CallToolResult` serializers — roughly 3x the boilerplate per tool across 28 tools.
