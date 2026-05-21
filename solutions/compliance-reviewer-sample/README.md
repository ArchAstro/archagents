# Compliance Reviewer Sample

Reviews pull requests against compliance rules — does not review style or bugs.

## Architecture

![Architecture overview](diagrams/architecture.svg)

## Install

```sh
archagent install agentsample compliance-reviewer-sample
```

## Bundle layout

- `agents/compliance-reviewer-sample.yaml` — deployable AgentTemplate with custom tools/routines referenced by `template_path`
- `solution.yaml` — catalog Solution wrapper and template manifest
- `tools/` — standalone AgentToolTemplate configs for custom tools
- `routines/` — standalone AgentRoutineTemplate configs for substantive routines
- `env.example` — local reference for required environment variables
- `examples/` — bundled sample support files
- `rules/` — bundled sample support files
- `scripts/` — bundled sample support files

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/compliance-reviewer-sample
```

## Knowledge files

This Solution includes seed markdown files as bundle assets. Because Solution imports publish library templates rather than provisioning a runtime agent, attach these files to the `archastro/files` installation after installing the agent template.
