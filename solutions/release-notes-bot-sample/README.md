# Release Notes Bot Sample

Drafts the weekly changelog by scanning merged PRs on a schedule.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample release-notes-bot-sample
```

## Bundle layout

- `agents/release-notes-bot-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `tools/` — standalone AgentToolTemplate configs for custom tools
- `routines/` — standalone AgentRoutineTemplate configs for substantive routines
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `scripts/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/release-notes-bot-sample
```
