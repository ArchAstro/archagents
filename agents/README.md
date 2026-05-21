# Agent Template Compatibility Paths

The catalog samples are authored under [`solutions/`](../solutions/). This
directory keeps the historical `agents/<slug>/` template paths alive for
onboarding flows and other callers that still read templates directly from
this repo.

Each `agents/<slug>/` directory is a thin compatibility wrapper:

- `agent.yaml` is a symlink to the shared AgentTemplate in the matching
  Solution bundle.
- Supporting folders such as `tools/`, `routines/`, `scripts/`, `skills/`,
  and `knowledge/` are symlinked when the shared AgentTemplate references
  them.
- There is intentionally no `sample.yaml` here. Release/catalog samples are
  built from `solutions/<slug>-sample/`.

Install samples from the Solution slugs:

```bash
archagent install agentsample code-review-agent-sample
archagent install agentsample security-triage-agent-sample
```

Use these compatibility paths only when a workflow needs to load a template
file directly, for example `agents/archastro-onboarding/agent.yaml`.
