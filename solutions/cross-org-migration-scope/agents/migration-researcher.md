# Migration Researcher

Customer-side investigator for scoping a vendor's breaking-change
migration. It works the Orchestrator's search requests against its
**own organization's codebase** to (1) identify the areas at risk of
breaking and (2) confirm or write the classic (pre-migration) **paper
test** for each affected use case in the shared paper-test repo.

Its goal: the paper tests **accurately reflect real-world usage** —
asserting on the behaviors and dependencies the customer's production
code actually relies on, not merely that a call happens. Later steps
of the migration replay these tests to prove the migration is safe
before real usage is moved.

Findings are evidence-first: call-site tables with `file:line`, a
mandatory coverage manifest recording the git SHA scanned, and
explicit negative results. It never mints use-case IDs or decides what
the breaking changes are — that authority belongs to the Orchestrator.
Every outgoing finding and every repo change passes a human review
gate.

## Two execution modes

- **Hosted session** — platform builtin tools, plus GitHub repo
  operations (`get_repo_file`, `create_branch`, `commit_file`,
  `create_pull_request`) surfaced through the `integrations` tool once
  a GitHub App integration is connected to the agent.
- **Local automated session (astrorun)** — the agent runs as a local
  coding session inside a working clone of the codebase under
  investigation: it investigates with local shell/`git grep` and posts
  findings and manages tasks by shelling out to the
  `archastro`/`archagent` CLIs. With the GitHub App bound, the same
  `integrations` repo operations are available here too; without it,
  the local `gh`/`git` CLIs are the fallback for the paper-test repo.

GitHub access in both modes comes from the org's GitHub App connection
bound to the agent (an `enablement/github_app` agent installation).
Sessions load their tool manifest at start, so bind it before
launching. The identity prompt tells the agent to detect what it has
from the tools actually available.

## Contract with the workflow

When driven by the `migration-scope-investigation` automation, the
embedded work item asks for a strict JSON reply (`finding`,
`paper_test`, `pr_url`). The agent returns only that JSON object — the
workflow parses it mechanically.
