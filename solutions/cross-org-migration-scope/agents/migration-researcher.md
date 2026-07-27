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
In interactive sessions, outgoing findings and repo changes pass a
human review gate; an embedded work item is pre-authorized by its
dispatch and returns its JSON result directly, with concerns routed to
the finding's Open questions (repo changes still go through a PR in
every mode).

## Two execution modes

- **Hosted session** — platform builtin tools, plus GitHub repo read
  operations (get contents, get tree, search code) surfaced through
  the `integrations` tool once the GitHub App is bound to the agent,
  and any write-capable tools the installer adds.
- **Local automated session (astrorun)** — the agent runs as a local
  coding session inside a working clone of the codebase under
  investigation: it investigates with local shell/`git grep`, and for
  platform actions (task updates, thread posts) uses whatever platform
  tools the session surfaces, shelling out to the
  `archastro`/`archagent` CLIs as the fallback. With the GitHub App
  bound, the same `integrations` read operations are available here
  too.

GitHub reads in both modes come from the org's GitHub App connection
bound to the agent (the template declares the `enablement/github_app`
installation; sessions load their tool manifest at start, so bind
before launching). Branch/commit/PR **writes** are a different story:
the `integrations` builtin has no write operations, so writes use the
local `gh`/`git` CLIs in astrorun sessions — or a write-capable custom
tool the installer connects for hosted sessions. The identity prompt
tells the agent to detect what it has from the tools actually
available.

## Contract with the workflow

When driven by the `migration-scope-investigation` automation, the
embedded work item asks for a strict JSON reply (`finding`,
`paper_test`, `pr_url`). The agent returns only that JSON object — the
workflow parses it mechanically. A first-pass discovery request (no
use-case ID minted yet) legitimately returns `paper_test: "none"`; the
Orchestrator mints the ID from the finding and follows up with a keyed
request that lands the test.
