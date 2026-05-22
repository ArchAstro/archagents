# ArchAstro Onboarding Sample

Walks a new ArchAstro user through deploying their first agent. The
agent reads `docs.archagents.com`, drives a step-by-step setup
conversation, and writes the user's agent config end-to-end.

> The runtime onboarding agent is created by the app's onboarding
> flow, not by `archagent install` alone. Installing this sample
> publishes the templates the app uses.

## Architecture

![Architecture overview](diagrams/architecture.svg)

The app's onboarding flow starts the agent in a fresh thread. The
agent fetches relevant docs pages, runs a guided wizard prompt, and
writes the user's first agent config.

## Install

```sh
archagent install agentsample archastro-onboarding-sample
```

## Required env vars

None. The bundled docs-fetch script hits public `docs.archagents.com`
endpoints and does not require credentials. Store any user-supplied
secrets through ArchAstro env vars, not in prompts or scripts.

## Bundle layout

- `agents/archastro-onboarding-sample.yaml` — the agent config
- `solution.yaml` — catalog metadata
- `tools/` — the `docs-fetch` tool that retrieves `docs.archagents.com` pages
- `skills/` — the `archastro-onboarding` skill (a multi-step setup wizard the agent loads on demand)
- `prompts.md` — prompt templates for each onboarding step
- `scripts/` — implementation of the docs-fetch tool
- `env.example` — no required env vars

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/archastro-onboarding-sample
```
