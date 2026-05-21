# Agent Samples Moved

The sample bundles now live under [`solutions/`](../solutions/). Each
bundle is a catalog-facing Solution that imports a deployable
AgentTemplate plus any custom tool and routine templates it needs.

Use the Solution slugs when installing from releases:

```bash
archagent install agentsample code-review-agent-sample
archagent install agentsample security-triage-agent-sample
```

`agents/` is kept only as a stable documentation landing page.
