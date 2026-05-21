# Cross-Org Collaboration Agent Sample

A code-aware engineering agent that participates in cross-org threads with field guards enforced.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample cross-org-collab-agent-sample
```

## Bundle layout

- `agents/cross-org-collab-agent-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `tools/` — standalone AgentToolTemplate configs for custom tools
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `schemas/` — bundled sample support files
- `scripts/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/cross-org-collab-agent-sample
```
