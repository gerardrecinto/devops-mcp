# Contributing

## Dev setup

Needs Python 3.11 or newer.

```bash
git clone https://github.com/gerardrecinto/devops-mcp.git
cd devops-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run the checks

CI runs these, so run them before you open a PR:

```bash
ruff check src/ tests/
black --check src/ tests/
pytest tests/ -v
```

Run one file while you work, for example `pytest tests/test_jenkins.py`.

## Add a tool module

1. Create `src/devops_mcp/tools/<name>.py` with `register(mcp, audit)`. Copy `jenkins.py` or `servicenow.py` for the shape.
2. Register tools with `@mcp.tool()`, return a JSON string, and call `audit("<tool_name>", {...})` first. Never put secrets or message bodies in the audit params.
3. Without credentials, return `not_configured("<Service>")` from `devops_mcp.demo`. If you add sample data, wrap it with `demo_response` so it is labelled.
4. Keep tools read-only. Anything that sends or changes data must check `writes_enabled()` and be called out in the README security table.
5. Add the module to the `modules` list and `_CONFIG_ENV` in `server.py`.
6. Add `tests/test_<name>.py`, and add each tool to a table in `README.md`. `tests/test_readme.py` fails if the README and the registered tools disagree.

Exceptions inside a tool are turned into `{"error", "message", "hint"}` by the server, so you do not need a blanket try/except.

## Starter ideas

These come from the README roadmap:

- Grafana alert history: list firing and recently resolved alerts for a folder or label.
- PagerDuty incident lookup: open incidents and who is on call, read-only.
- ArgoCD sync status: is an application synced, degraded or out of sync, and since when.
- Terraform state drift: run a plan against a state file and report the resources that differ.
- SSE transport: serve the same tools over SSE as well as stdio, behind a flag.
