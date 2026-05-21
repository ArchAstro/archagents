## Sample GitHub event alert (posted to Slack)

### When a new P1 issue opens

```
🚨 *Issue #4360 opened by @dana — "Analytics charts render empty for
new orgs"*

Title-tagged P1. Reproducible on staging when an org has no events in the
selected window. Suggested owner: @dana (recent author of apps/web/charts
in PR #4321).
```

### When a PR closing the issue is merged

```
✅ *Resolved* — PR #4334 (merged) closes issue #4360. Auto-cleared from
the alert tracking — future closure events for this issue won't re-fire.
```

### When the issue would have been opened but is filtered out

(Nothing posted to Slack — the agent emits `SKIP: P3 + Polish, not alerting`
internally, and the delivery script suppresses it.)

## What's happening behind the scenes

1. GitHub webhook fires (`webhook.github_app.issues` or
   `webhook.github_app.pull_request` or `webhook.github_app.workflow_run`).
2. `ph-github-event-alert.aascript` runs:
   - Skips events from any repo other than `MONITORED_REPO`.
   - For issue close/reopen events, pre-fetches `alerted_issue_<N>` from
     storage and embeds the result in the prompt — saves a tool call.
   - Constructs an event-specific prompt with explicit response rules:
     "alert in 2-3 sentences" or "respond with `SKIP: <reason>`".
   - Posts the prompt to the `health-alerts` thread.
3. The agent generates a response per the prompt rules:
   - **For new problems**: writes `working_memory_set('alerted_issue_<N>', ...)`
     and emits the alert text.
   - **For closures with prior alerts**: emits `✅ resolved` and calls
     `working_memory_delete` to clear the matched key.
   - **For closures with no prior alert** (the common case): emits
     `SKIP: no prior alert for this closure`.
   - **For routine noise** (P3-Polish, dependency bumps, bot issues): emits
     `SKIP: <reason>`.
4. `ph-deliver.aascript` forwards the cleaned response, suppressing
   `SKIP:`-prefixed messages.

## Memory-gating in one diagram

```
issue.opened    →  agent alerts + writes alerted_issue_N=<reason>
issue.closed    →  script pre-fetches alerted_issue_N
                  ├─ value present  → agent posts "✅ resolved" + deletes key
                  └─ value null     → agent posts "SKIP: no prior alert"
issue.reopened  →  script pre-fetches alerted_issue_N
                  ├─ value present  → agent posts re-escalation
                  └─ value null     → agent posts new-problem alert
pr.merged       →  agent scans body for `fixes #N`, working_memory_get for each
                  ├─ any match      → "✅ resolved" + delete matched keys
                  └─ no match       → SKIP
ci.failed       →  alert if main, or pattern across PRs; else SKIP
```

This makes the alert stream high-signal: closures and merges only post when
they resolve something we previously cared about; new alerts dedupe via
`alerted_issue_<N>`; reopens distinguish "fresh problem" from "we knew
about this."
