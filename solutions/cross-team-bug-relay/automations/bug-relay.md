# Cross-Team Bug Relay (automation)

An **invocable, org-level automation** — no agent anchor — wrapping the
`bug-relay` durable workflow. Installing it provisions the automation
already activated; invoking it starts one relay run.

## Invoke payload

```json
{
  "parameters": {
    "title": "One-line defect summary",
    "details": "Symptom, error strings, identifiers, severity…",
    "thread": "thr_… (optional — status updates post here)"
  },
  "participants": {
    "reporter": "agi_… (Bug Reporter agent)",
    "resolver": "agi_… (Bug Resolver agent)"
  }
}
```

## What a run does

1. Posts "relay started" to the thread (when provided).
2. Parks a **Discovery** work item on the reporter's queue; the
   reporter's harness claims it, files the issue, submits JSON.
3. Posts "filed", then parks **Triage** on the resolver's queue.
4. Switches on the resolver's `resolution`: `attempt_workaround` parks
   **Remediation** back on the reporter; anything else posts a manual
   follow-up notice.
5. Posts the final outcome. The full journey is durable — inspect it
   with the automation run's journal.

## Cross-org note

Work items may only be assigned to an agent outside the run's org when
this automation carries an `assign` ACL grant naming that agent (or its
org). Publish one with
`archastro update automation cross-team-bug-relay --acl-add agent:<id>:assign`.
