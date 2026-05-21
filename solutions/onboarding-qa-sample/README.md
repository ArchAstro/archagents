# Onboarding Q&A Sample

Answers new-hire questions about how things work at the company.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample onboarding-qa-sample
```

## Bundle layout

- `agents/onboarding-qa-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `knowledge/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/onboarding-qa-sample
```

## Knowledge files

This Solution includes seed markdown files as bundle assets. Because Solution imports publish library templates rather than provisioning a runtime agent, attach these files to the `archastro/files` installation after installing the agent template.
