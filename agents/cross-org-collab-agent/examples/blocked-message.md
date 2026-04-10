# Example: a message that gets BLOCKED by the field guards

A message the agent might *want* to send (because it's helpful) but
that would leak implementation details. Each example shows which
guard layer rejects it.

## Example 1: contains a `defmodule` (Layer 1, RegexMatch)

```json
{
  "classification": "PUBLIC",
  "message_type": "design_proposal",
  "summary": "Here's our billing module:",
  "interface_shape": "defmodule App.Billing.MeterReporter do\n  use GenServer\n  def report_tokens(...)\nend",
  "safety_self_check": { ... all true ... }
}
```

**Blocked at Layer 1.** Regex `defmodule\\s+[A-Z][\\w.]*` matches the
`interface_shape` field. The agent gets:
> Layer-1 RegexMatch rejected: Contains Elixir module definition

## Example 2: contains an internal path (Layer 2, ContainsAny)

```json
{
  "classification": "PUBLIC",
  "summary": "We're going to add this in services/internal/billing/meter.ex",
  "safety_self_check": { ... all true ... }
}
```

**Blocked at Layer 2.** ContainsAny matches `services/internal/`. The agent gets:
> Layer-2 ContainsAny rejected: Contains internal repo path

## Example 3: subtle code leak (Layer 3, LLM Judge — Claude)

```json
{
  "classification": "PUBLIC",
  "summary": "We use a GenServer with handle_cast for the buffer, batched on a 2-minute timer, with retry logic via exponential backoff.",
  "safety_self_check": { ... all true ... }
}
```

**Passes Layers 1-2** (no `defmodule`, no path, no secret patterns)
but the **Claude judge rejects it** because mentioning `GenServer`
and `handle_cast` reveals Elixir-specific implementation details.

## Example 4: passes blacklists, fails whitelist (Layer 4, LLM Judge — GPT)

```json
{
  "classification": "PUBLIC",
  "summary": "Our billing system runs on Kubernetes with 3 replicas in us-central1-a, behind an internal load balancer, with Cloud SQL for persistence and Memorystore for caching. We deploy via Cloud Build twice a day.",
  "safety_self_check": { ... all true ... }
}
```

**Passes Layer 1** (no code patterns), **Layer 2** (no specific paths/env vars),
**Layer 3** (no source code per Claude). But **Layer 4 (GPT) rejects it**
because it doesn't fall into any of the 5 whitelisted categories
(architecture descriptions don't include infrastructure details, deployment
configs, region info — those are internal infrastructure).

This is where the cross-vendor judge matters: a prompt injection that
exploits Claude's tendency to "be helpful" might bypass the Claude
judge, but the strict whitelist GPT judge catches it.

## Example 5: agent forgets to self-attest (Layer 5, LLM Judge — verification)

```json
{
  "classification": "PUBLIC",
  "summary": "Architecture-level explanation of our integration approach.",
  "safety_self_check": {
    "no_source_code": true,
    "no_internal_paths": true,
    "no_secrets_or_env_vars": true,
    "no_infrastructure_details": false,
    "architecture_level_only": true
  }
}
```

**Blocked at Layer 5.** The verification judge sees that
`no_infrastructure_details: false` and rejects. The agent admitted via
its own self-check that the message contains infrastructure details —
it can't fool the judge by setting all booleans to true after the fact
either, because the regex on the body would re-fail in Layers 1/2.

---

## What this demonstrates

Five independent layers, each catching a different class of leak.
Bypassing any one is hard. Bypassing all five — including two LLM
judges from different vendors — is exponentially harder.

The agent gets the rejection reason and can rewrite. The partner
never sees the unsafe draft.
