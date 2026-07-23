# Migration Researcher

Integrator-side investigator for Process 1 (Scope) of a coordinated
integration migration. It works the Orchestrator's search requests
against its **own organization's codebase**, confirms or writes the
classic (pre-migration) **paper test** for each affected use case, and
reports evidence-first findings — call-site tables with `file:line`, a
mandatory coverage manifest recording the git SHA scanned, and explicit
negative results.

It never mints use-case IDs or decides what the breaking changes are —
that authority belongs to the Orchestrator. Every outgoing finding and
every repo change passes a human review gate.

## Two execution modes

- **Hosted session** — platform builtin tools, plus GitHub repo
  operations (`get_repo_file`, `create_branch`, `commit_file`,
  `create_pull_request`) surfaced through the `integrations` tool once
  a GitHub App integration is connected to the agent.
- **Local automated session (astrorun)** — the agent runs as a local
  coding session inside a working clone of the codebase under
  investigation, with no platform tools: it investigates with local
  shell/`git grep`, writes paper tests via the local `gh`/`git` CLIs,
  and posts findings and manages tasks by shelling out to the
  `archastro`/`archagent` CLIs.

The identity prompt tells the agent to detect its mode from the tools
actually available.

## Contract with the workflow

When driven by the `migration-scope-investigation` automation, the
embedded work item asks for a strict JSON reply (`finding`,
`paper_test`, `pr_url`). The agent returns only that JSON object — the
workflow parses it mechanically.
