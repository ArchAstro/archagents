# Bug Reporter

Tracker-side specialist for the cross-team bug relay. It runs two of the
relay's embedded stages:

- **Discovery** — confirms the reported symptom, records the defect in
  the team's issue tracker, and captures concrete reproduction steps.
- **Remediation** — applies the workaround guidance the owning team's
  resolver produced, and records the outcome on the tracked issue.

## Tracker-agnostic by design

The template ships with builtin tools only (memory, knowledge search,
artifacts, skills, integrations). Connect your tracker however your team
works — an MCP server, a custom tool, or an integration — and the agent
uses it. With no tracker connected it still produces fully-formatted
issue bodies marked `pending-manual-filing`, so the relay never stalls
on missing tooling.

## Contract with the workflow

Embedded work items ask for a strict JSON reply (issue reference, URL,
summary, reproduction steps — or remediation outcome). The agent returns
only that JSON; the workflow parses it mechanically and templates the
next stage's instructions from it.
