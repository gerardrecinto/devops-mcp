# Changelog

All notable changes are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.4.0] - 2026-11-06

### Added
- Optional step order, so a post to Slack or Teams waits for a real read of the system it reports on.
- Tracing and SLO helpers (optional `otel` extra).
- A reusable deploy workflow with an approval gate.

### Changed
- Workflow actions are pinned to commit SHAs.
- Release assets now include the wheel, the sdist and `SHA256SUMS`.

## [1.3.1] - 2026-10-28

### Changed
- The container image is published for `linux/arm64` as well as `linux/amd64`.

## [1.3.0] - 2026-10-28

### Fixed
- Tools no longer invent data when a backend is unreachable.
- Crash-looping pods are caught by the Kubernetes tools.

### Security
- Hardened the webhook handler and the audit log.

## [1.2.1] - 2026-10-28

### Added
- A GitHub Pages site with an in-browser demo.

### Fixed
- CI lint failures and several Jenkins tool bugs (URL quoting, nested folder jobs, failing-and-rebuilding state).
- Long paths and argument names wrap on phone widths.
- The Release workflow can be run by hand with a version input.

## [1.2.0] - 2026-08-20

### Fixed
- Startup crash against `mcp` SDK 2.0.0. The server tries the 2.x import path first and falls back to 1.x.

### Added
- `docs/architecture.md` with sequence and flow diagrams.

## [1.1.0] - 2026-07-01

### Fixed
- CI was red on main: the Kubernetes and AWS modules now check for real credentials before making a live call.

### Changed
- Hardened CI, dependencies and the container image.

## [1.0.0] - 2026-06-11

### Added
- Read-only tools for Kubernetes, Jenkins, GitHub Actions, AWS, Azure, GCP, ServiceNow, Slack and Microsoft Teams.
- An audit log of every tool call.
- Per-module loading, so one failed integration does not stop the others.
- A container image at `ghcr.io/gerardrecinto/devops-mcp`.
