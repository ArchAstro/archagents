## Sample daily report (posted to Slack)

```
*TL;DR* — Main is green. 2 issues opened overnight (analytics regression, billing
edge case). Last week's auth refactor (#4180) closes 3 open issues that should be
verified and closed.

*Notable*
- PR #4334 may close issue #4329 (signup-flow regression flagged Friday). Verify
  fix on staging before closing the issue.
- Issue #4360 (Analytics) opened 02:14 UTC — chart renders empty for orgs with
  no events in the selected window. Suggested owner: @dana (last touched
  apps/web/charts in PR #4321).

*CI Status*
All green on main. Synthetic test suite passing.

*Issues needing attention (grouped)*
- Analytics (issue #4360, #4357): empty-state regressions. Suggested owner: @dana.
- Billing (issue #4358): proration edge case for org downgrades. Suggested
  owner: @marc.
- Infrastructure (issue #4321): pod restart loop in staging webhooks. Already
  assigned to @kim.

*Possibly resolved*
- Auth (issue #4180, #4181, #4182): all referenced as fixed in PR #4334
  (merged 23:45 UTC). Verify on staging.

*Customer fixes/ships (since 2026-04-25 09:00 UTC)*
- API (PR #4334): bot accounts can now refresh tokens without re-auth.
- Portal (PR #4341, #4342): faster initial load on the agent details page.
- Webhook reliability (PR #4339): retries now use jittered backoff, fewer
  spurious 429s reported by integrators.

*Notable activity*
- 14 PRs merged in the last 24h (12 from @org members, 2 from external
  contributors via fork).
```

## What's happening behind the scenes

1. At 09:05 UTC, `ph-health-report-prompt.aascript` fires:
   - Reads `last_report_summary` from storage (yesterday's continuity block).
   - Builds the prompt embedding today's date and yesterday's summary.
   - Posts the prompt to the `health-reports` thread.
2. The `participate` routine sees the new message and the agent generates a
   reply against its identity + tools (GitHub search, long-term memory, etc.).
3. `ph-deliver.aascript` fires on the agent's response:
   - Strips `<thought>`/`<thinking>`/`<summary>` blocks.
   - Forwards the cleaned content to `SLACK_OUTPUT_CHANNEL` as Slack mrkdwn.
4. `ph-capture.aascript` fires on the same response:
   - Extracts the `<summary>...</summary>` block.
   - Writes it to storage under `last_report_summary` (3-day TTL).
5. Tomorrow 09:05 UTC, step 1 repeats — but with yesterday's summary embedded.
