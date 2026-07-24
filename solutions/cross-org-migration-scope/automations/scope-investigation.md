# Migration Scope Investigation (automation)

An **invocable, org-level automation** — no agent anchor — wrapping the
`scope-investigation-workflow` durable workflow. Installing it
provisions the automation already activated; invoking it dispatches one
breaking-change search request to a customer-side Researcher agent.

## Invoke contract

The automation's `input_schema_ref` validates the payload directly:

```json
{
  "request": "Search request MIGRATION-38c6b758 (scoping). Find every call site that reads … Confirm or write the classic paper test and KEY IT to MIGRATION-38c6b758 …",
  "thread": "thr_… (optional — the finding posts here)"
}
```

**Pass the real request text — the one the Orchestrator posts to the
thread — as `request`.** The embedded Researcher only ever sees
`{{$.request}}`, so the use-case ID and marker conventions must be *in*
that string; a stripped summary produces a paper test with no use-case
marker.

Participant assignment is a top-level sibling of `payload` in the
invoke request. With the CLI:

```sh
archastro invoke automation migration-scope-investigation --payload '{
  "request": "Search request MIGRATION-… (scoping). Find every call site that …",
  "thread": "thr_…"
}' --participants '{
  "researcher": "agi_…"
}'
```

## What a run does

1. Parks an **investigation** work item on the researcher's queue. A
   hosted researcher's harness claims it; in a local setup the
   customer runs `astrorun`, which leases it and runs the
   investigation inside a working checkout:

   ```sh
   archastro list workflow-work --agent <researcher>
   archastro claim workflow-work --agent <researcher>
   ```

2. The researcher submits a strict JSON result (`finding`,
   `paper_test`, `pr_url`) that resumes the run.
3. The finding is posted to the payload `thread` when one was provided.
   The full journey is durable — inspect it with the automation run's
   journal.

## Cross-org dispatch

Work items may only be assigned to an agent outside the run's org when
this automation carries an `assign` ACL grant. Use an **org** principal
naming the researcher's org:

```sh
archastro update automation migration-scope-investigation \
  --acl-add org:<researcher-org-id>:assign
```
