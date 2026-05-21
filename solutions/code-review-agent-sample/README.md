# Code Review Agent Sample

A senior engineer that reviews every PR like it's going into production at 3am.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample code-review-agent-sample
```

## Bundle layout

- `agents/code-review-agent-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `tools/` — standalone AgentToolTemplate configs for custom tools
- `routines/` — standalone AgentRoutineTemplate configs for substantive routines
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `scripts/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/code-review-agent-sample
```
