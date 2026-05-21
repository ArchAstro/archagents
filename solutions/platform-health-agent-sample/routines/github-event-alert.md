# GitHub Event Alert

Reacts to GitHub webhook events (issues opened/closed/reopened, PR
closed+merged, CI failures) by prompting the agent in the
`health-alerts` thread. Memory-gated: new problems write
`alerted_issue_<N>` / `alerted_ci_*` keys via `working_memory_set`;
closures look up the matching key and only post a "✅ resolved"
update on a hit. For issue close/reopen events the script
pre-fetches memory state via `storage.get` and embeds it in the
prompt to remove an LLM tool call.


- Event: `webhook.github_app.*`
- Handler: `script`
