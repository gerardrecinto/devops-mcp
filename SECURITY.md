# Security Policy

## Reporting a vulnerability

Email gerardrecinto@gmail.com with "devops-mcp security" in the subject. Please do not open a public issue for a vulnerability.

Include what you found, how to reproduce it, and the version (`devops_mcp_health` or the startup log shows it). If you can, say whether it needs credentials or only a crafted tool call.

You can expect an acknowledgement within 7 days. This is a one-maintainer project, so a fix timeline depends on severity, but I will tell you what I plan to do and credit you in the release notes if you want that.

## Supported versions

Only the latest 1.x release gets security fixes. Older minor versions do not.

## What is in scope

- A tool call that writes, deletes or triggers something when it should not (the only intended writes are Slack and Teams posts, off unless `DEVOPS_MCP_ENABLE_WRITES=1`).
- Ways to make the server send data to a host the operator did not configure, for example through a model-supplied `webhook_url`.
- Secrets showing up in the audit log, tool output or container image.
- Problems in the release workflow or published image.

## Out of scope

- Access the operator already granted through their own credentials. The server can only do what those credentials allow, so give it read-only credentials.
- Sample data returned in demo mode.
