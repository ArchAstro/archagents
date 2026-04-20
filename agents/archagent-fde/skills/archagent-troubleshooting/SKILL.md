---
name: archagent-troubleshooting
description: Debugging playbook for ArchAgents — agents not triggering, scripts failing validation, config deploys not syncing, memory not persisting, routines not firing, credentials expired. Use when the customer says "it's not working", "my agent didn't fire", "this script fails", or when you see a CLI error you need to diagnose.
---

# ArchAgents Troubleshooting

When something is broken, diagnose in this order. Most issues resolve
in the first three steps.

## Step 1 — Check auth and CLI state

```
archagent auth status
archagent --version
```

Common findings:
- `Status: Expired` → `archagent auth login`
- CLI older than `plugin-compatibility.json` minimum → reinstall via
  the `archagent-install` skill.
- Wrong app selected → `archagent auth app list` and
  `archagent auth app set <id>`.

## Step 2 — Validate configs before assuming deploy succeeded

```
archagent validate config -k AgentTemplate -f agent.yaml
archagent validate config -k Script -f scripts/foo.aascript
```

Validation errors surface the exact field that failed. Fix locally,
re-validate, then redeploy. Do not trust that a deploy succeeded just
because the CLI exited 0 — validate explicitly.

## Step 3 — Confirm server state matches local

```
archagent describe agent <agent-key>
archagent describe config -k Script <script-slug>
```

If the server version is older than what you expect, the last
`archagent deploy configs` / `deploy agent` did not include the file.
Re-run the deploy. If the server version is newer than local, pull:

```
archagent sync configs
```

## Common symptoms and fixes

### "The agent didn't respond in the thread"

1. Is there a `thread.session.join` routine with `preset: participate`?
   Without it, the agent sits silent.
2. Is the agent installed in the thread? Check
   `archagent list threadmembers --thread <id>`.
3. Does the routine have `status: active`?

### "The scheduled routine didn't fire"

1. Both `schedule: "<cron>"` and `event_type: schedule.cron` must be
   set at the routine level. The most common bug is putting the
   schedule under `event_config.schedule`, where it is silently
   ignored.
2. Timezone: cron runs in UTC. "9am Monday" is `0 9 * * 1` UTC, not
   your local 9am.
3. `archagent list routineexecutions --routine <id>` shows whether it
   fired.

### "The webhook routine didn't fire"

1. The webhook URL — copy it from `archagent describe routine <id>`.
   There is exactly one per routine; do not guess it.
2. `archagent list routineexecutions` shows inbound requests even
   when the handler errors. If there is no execution record, the
   webhook never reached the platform.
3. Filters: an overly narrow `filters` block can drop the event.
   Start with `filters: {}` and narrow once it works.

### "The script fails at runtime"

1. Test it standalone:
   ```
   archagent test script <slug> --input '{"key": "value"}'
   ```
2. The script language has no `return` statement — the last expression
   is the result. If you wrote `return x`, it fails to parse.
3. Use `unwrap(...)` on `http.get / http.post` responses; the raw call
   returns a `Result`, not the response body.
4. Consult `archagent describe scriptdocs` for the exact namespace
   API before guessing.

### "Custom tool doesn't appear on the agent"

1. `config_ref` must match the deployed Script's slug, not its
   display name or ID.
2. The script must be deployed BEFORE the AgentTemplate that
   references it — run `archagent deploy configs` first if the
   agent has custom tools.
3. `status: active` on the tool entry.

### "Memory isn't persisting"

1. The `memory/long-term` installation must be attached in
   `installations:`.
2. The `long_term_memory` tool must be granted in `tools:`.
3. The agent must actually call it — check identity prompt.
4. Inspect: `archagent list memories --agent <id>`.

### "My changes to agent.yaml aren't showing up"

The agent must be redeployed:
```
archagent deploy agent agent.yaml
```

`deploy configs` and `deploy agent` are different commands. `deploy
configs` syncs the `configs/` directory (Scripts, Skills, etc.) but
does not redeploy an existing agent from a template.

## When you're stuck

1. Run the failing command with `-v` or `--verbose` if supported.
2. `archagent describe agent <id> -o json` — the full server-side view.
3. `archagent list agentsessions --agent <id>` — past runs and their
   error states.
4. If the CLI itself is misbehaving, reinstall via the `archagent-install`
   skill and re-auth. Do not edit credential files directly.
5. Escalate to `hi@archastro.ai` with: the agent ID, the routine ID,
   the exact timestamp of the failure, and the CLI output. Do not
   send credentials.

## Response rules

- Always diagnose before fixing. "I'm going to try X" without a
  read is guessing.
- When you find the root cause, say what it was. Customers learn
  the platform through debugging.
- Never suggest workarounds that skip validation (`--no-validate`,
  `--force`) without being explicit that it is a workaround.
