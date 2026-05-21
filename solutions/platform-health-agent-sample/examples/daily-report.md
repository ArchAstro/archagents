## Sample daily report (posted to Slack)

```
*TL;DR* — Main is green. Two analytics regressions opened overnight; auth
stack from last week now fully merged.

*Notable*
- [issue #4360](https://github.com/your-org/your-repo/issues/4360): Analytics
  charts render empty for new orgs (P1 overnight). Suggested owner: @dana.
- [PR #4334](https://github.com/your-org/your-repo/pull/4334) closes
  [issue #4329](https://github.com/your-org/your-repo/issues/4329) (signup-flow
  regression). Verify on staging.

*CI Status*
All green on main.

*Issues needing attention*
- Analytics ([issue #4360](https://github.com/your-org/your-repo/issues/4360),
  [issue #4357](https://github.com/your-org/your-repo/issues/4357)) → @dana
- Billing ([issue #4358](https://github.com/your-org/your-repo/issues/4358)) → @marc
- Infrastructure ([issue #4321](https://github.com/your-org/your-repo/issues/4321)) → @kim

*Possibly resolved*
- [issue #4180](https://github.com/your-org/your-repo/issues/4180) — closed by
  [PR #4334](https://github.com/your-org/your-repo/pull/4334) (merged 23:45 UTC).
  Comment posted on the issue with resolution evidence.

*Customer fixes/ships (since 2026-04-25 09:00 UTC)*
- API ([PR #4334](https://github.com/your-org/your-repo/pull/4334))
- Portal ([PR #4341](https://github.com/your-org/your-repo/pull/4341),
  [PR #4342](https://github.com/your-org/your-repo/pull/4342))
- Webhook reliability ([PR #4339](https://github.com/your-org/your-repo/pull/4339))
```

> Note: the `your-org/your-repo` URLs above are placeholder values for
> documentation. In your Slack channel, the agent renders real links to
> whatever you set `MONITORED_REPO` to (e.g. `https://github.com/<your-owner>/<your-repo>/issues/<N>`).

## What's happening behind the scenes

1. At 09:05 UTC, `ph-health-report-prompt.aascript` fires:
   - Reads `last_report_summary` from storage (yesterday's continuity block).
   - Splits `MONITORED_REPO` into `owner`/`repo` and embeds them as concrete
     values in the prompt's link templates and `github_create_issue_comment`
     instructions.
   - Posts the prompt to the `health-reports` thread.
2. The `participate` routine sees the new message and the agent generates a
   reply against its identity + tool surface (working memory, the integrations
   builtin's GitHub tools, web search, etc.).
3. For any "Possibly resolved" item: the agent verifies the issue is still
   OPEN on GitHub, checks `working_memory_get(commented_on_issue_<N>)` for
   dedup, then calls `github_create_issue_comment` (the integrations-builtin
   tool, authenticating as the GitHub App's installation token — NOT the
   read-only `GITHUB_TOKEN` PAT) and stores a marker in working memory.
4. `ph-deliver.aascript` fires on the agent's response:
   - Strips `<thought>`/`<thinking>`/`<summary>` blocks via regex.
   - Forwards the cleaned content to `SLACK_OUTPUT_CHANNEL` as Slack mrkdwn.
5. `ph-capture.aascript` fires on the same response:
   - Extracts the `<summary>...</summary>` block via regex match.
   - Writes it to storage under `last_report_summary` (3-day TTL).
6. Tomorrow 09:05 UTC, step 1 repeats — with yesterday's summary embedded.
   Issues already in working memory under `commented_on_issue_<N>` are
   skipped at step 3 so the agent doesn't re-comment.
