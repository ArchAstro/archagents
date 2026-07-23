# Cross-Org Migration Scope

A demo of **cross-org agent collaboration** on Process 1 (Scope) of a
coordinated integration migration: before anything is rewritten, two
companies map every place the integrator's code could break.

```
Orchestrator (vendor org) posts a search request to the shared thread
   │
invoke automation (payload: {request, thread?} + participants: {researcher})
   └─→ investigate (embedded: Researcher — possibly in ANOTHER ORG —
       │            finds call sites in its own codebase, confirms or
       │            writes the classic paper test, opens a PR)
       └─→ announce (posts the returned finding to the optional thread)
```

Each embedded stage is a durable, leaseable work item on the
Researcher's queue. Cross-org assignment is fail-closed until the
automation carries an `assign` ACL grant naming the researcher's org —
so the boundary crossing is explicit and auditable. The Researcher can
run **hosted** (GitHub ops via its `integrations` tool) or **locally
via `astrorun`** inside a working checkout, using only local
`git`/`gh`/`archastro` CLIs.

The shape is modeled on a real vendor×integrator billing-API migration
(e.g. Stripe classic → flexible billing mode), but the templates are
deliberately **engagement-agnostic**: the breaking-change catalog, the
use-case ID namespace (`FBM-…` by convention), and the repos involved
all arrive via the thread and the invoke payload.

## Layout

```
cross-org-migration-scope/
  sample.yaml                        # deploy steps (upload schema/workflow, deploy solution)
  solution.yaml                      # catalog wrapper + templates list
  agents/
    migration-orchestrator.yaml/.md  # vendor-side coordinator AgentTemplate
    migration-researcher.yaml/.md    # integrator-side investigator AgentTemplate
  automations/
    scope-investigation.yaml/.md     # invocable org-level AutomationTemplate
  schemas/
    scope-investigation-input.yaml   # invoke payload JsonSchema
  workflows/
    scope-investigation-workflow.yaml # the WorkflowGraph (embed node + announce)
```

## The working model

- **The thread is the record.** Requests, findings, registry updates,
  and rollups all land on one shared (cross-org team) thread.
- **The task list is the registry.** The Orchestrator mints a use-case
  ID per behavioral assumption (`FBM-` + 8 hex), tags a task with it,
  tracks lifecycle as task status, assigns the Researcher via
  `owner_agent`, and reconciles the reviewed finding as a task comment.
- **Findings are evidence-first.** Call-site tables with `file:line`, a
  mandatory coverage manifest recording the git SHA scanned, explicit
  negative results, and a classic paper test keyed to the use-case ID.
- **Pass the real request text down.** The embedded Researcher sees
  only the payload's `request` string — so the use-case ID and marker
  conventions must be in it, identical to what the Orchestrator posted
  on the thread.

## Try it

1. Validate and package:

   ```sh
   archastro validate solution .
   archastro package solution .
   ```

2. Import + install the three templates (multi-template Solution — pick
   each with `template`). Orchestrator in the vendor org, Researcher in
   the integrator org, then the automation in the vendor org.

3. Put both agents on a shared team thread, post a search request as
   the Orchestrator, and invoke an investigation (see
   `automations/scope-investigation.md` for the payload contract).
   Drive the embedded stage with the Researcher's harness — hosted, or
   the local demo loop:

   ```sh
   archastro list workflow-work --agent <researcher>
   archastro claim workflow-work --agent <researcher>
   ```

## Cross-org dispatch

Work items only cross an org boundary when the automation carries an
`assign` ACL grant. Use an **org** principal for the researcher's org:

```sh
archastro update automation migration-scope-investigation \
  --acl-add org:<researcher-org-id>:assign
```

## Demo tips (from the original runbook)

- **Silent setup, then record.** Orgs, agents, network, thread,
  automation, and grants are all setup — nothing posts to the thread.
  The demo-worthy sequence is: Orchestrator posts the request →
  invoke parks the work item → the integrator's astrorun leases it →
  the Researcher investigates, opens the paper-test PR, and its
  finding lands on the thread.
- **Pause `participate` routines during setup** so neither agent
  auto-replies to setup-era posts.
- **astrorun announce caveat:** the workflow's announce script posts
  under the invoking user's context. If the finding should appear
  authored by the Researcher itself, omit `thread` from the payload
  and include self-posting instructions (via the `archastro` CLI) in
  the `request` text instead.
- **Strict JSON matters.** A non-JSON result from the embedded session
  strands the durable run — the embed instructions demand exactly one
  JSON object.
