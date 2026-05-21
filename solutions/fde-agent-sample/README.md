# FDE Agent Sample

A production Forward Deployed Engineer agent for discovery, implementation, validation, and handoff.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample fde-agent-sample
```

## Bundle layout

- `agents/fde-agent-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `skills/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/fde-agent-sample
```
