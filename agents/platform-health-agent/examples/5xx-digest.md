## Sample 5xx digest (posted to Slack)

```
*Platform 5xx digest — last 24h: 47 errors across 5 signatures*

• `Ecto.NoResultsError` (18x) — likely related to PR #4329 (revert needed?
  introduced .one!/0 call against soft-deleted records).
   <https://console.cloud.google.com/logs/query;query=...|view 18 errors →>

• `Plug.Conn.AlreadySentError` (12x) — recurring from prior digests, no
  obvious match in open issues. Likely a known race in the request pipeline.
   <https://console.cloud.google.com/logs/query;query=...|view 12 errors →>

• `MyApp.Billing.GatewayError` (9x) — correlates with open issue #4358
  (proration edge case in downgrade flow).
   <https://console.cloud.google.com/logs/query;query=...|view 9 errors →>

• `Postgrex.Error` (5x) — connection pool exhaustion bursts. No obvious
  match.
   <https://console.cloud.google.com/logs/query;query=...|view 5 errors →>

• `MyApp.Webhook.DeliveryError` (3x) — likely fixed by PR #4339 (jittered
  backoff). Watch tomorrow's digest for the trend.
   <https://console.cloud.google.com/logs/query;query=...|view 3 errors →>

<https://console.cloud.google.com/logs/query;...|View all in Cloud Logging →>
```

## What's happening behind the scenes

1. At 14:30 UTC, `ph-5xx-digest.aascript` fires:
   - Mints a fresh GCP access token by signing a JWT with the SA private key
     and exchanging at `oauth2.googleapis.com/token`.
   - Queries Cloud Logging's `entries:list` for the last 24h of
     `severity>=ERROR` entries in the configured K8s namespace.
   - Groups entries by Elixir exception class via regex on
     `** (Module.Submodule.Class)`. Anything that doesn't match is bucketed
     under `(non-exception entry)` — we never fall back to message text
     because raw error messages can contain user input (emails, request
     paths) which would leak to Slack.
   - URL-encodes a per-signature drill-down link for each bucket. The
     encoder explicitly handles `>` and `<` because they're Slack mrkdwn
     link delimiters — an unencoded `>` in `severity>=ERROR` would close
     the `<url|label>` link prematurely.
   - Fetches recent open issues + recently merged PRs from GitHub via PAT.
   - Reads `last_5xx_digest_summary` from storage (yesterday's continuity).
   - Assembles a single prompt with all the data and posts it to the
     `5xx-digest` thread. **The agent makes ZERO additional tool calls.**
2. The agent formats a Slack-ready post per the prompt's instructions and
   appends a `<summary>` block.
3. `ph-deliver.aascript` strips internal blocks and forwards to Slack.
4. `ph-capture.aascript` writes the summary to `last_5xx_digest_summary`.

## Why no tool calls

Each tool call adds round-trip latency and a chance of hitting the
turn-coordinator timeout. By assembling everything the agent needs in
the prompt-emitter script, the agent's turn is short and predictable.
The agent's job is purely formatting + correlation — judgment-light
work that doesn't need exploration tools.
