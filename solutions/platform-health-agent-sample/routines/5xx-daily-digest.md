# 5xx Daily Digest

Cron-fires once per afternoon. Queries Cloud Logging for the last 24h
of ERROR-severity entries in the configured K8s namespace, groups by
Elixir exception class, pre-fetches recent open issues and merged PRs,
and prompts the agent (via participate on the `5xx-digest` thread) to
format a Slack post with per-signature drill-down URLs into the Cloud
Logging Console. The agent makes ZERO additional tool calls — all
data is in the prompt — to keep the turn fast.


- Event: `schedule.cron`
- Handler: `script`
