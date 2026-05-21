# Example: a message that PASSES all field guards

A clean architecture-level response from the agent in a cross-org thread.

```json
{
  "classification": "PUBLIC",
  "message_type": "design_proposal",
  "summary": "We have a billing context that exposes a usage reporting interface. When an agent run completes, it emits a token analytics event that flows through an async pipeline before reaching your Meter Events API. We preserve the original timestamp throughout, generate idempotency keys at ingestion time, and treat the no_customer_found webhook as a P1 alert.",
  "interface_shape": "report_usage(customer_id, event_name, value, occurred_at, idempotency_key) -> {ok, meter_event} | {error, reason}",
  "proposed_approach": "We'll create two meters: one for input tokens, one for output tokens. Granularity is org-level. We'll validate the customer ID at ingestion (before the buffer) so we catch missing-customer cases upstream of the silent-drop path.",
  "questions_for_partner": [
    "Is the 24-hour idempotency dedup window a hard boundary, or could we use longer retry windows?",
    "What's the recommended threshold for switching from /v1/billing/meter_events to the v2 stream endpoint?"
  ],
  "next_steps": [
    "Pin down the meter event_name strings so we can configure them in your dashboard",
    "Confirm the beta header version we should send",
    "Schedule a sync once we have the meters configured to validate the integration"
  ],
  "safety_self_check": {
    "no_source_code": true,
    "no_internal_paths": true,
    "no_secrets_or_env_vars": true,
    "no_infrastructure_details": true,
    "architecture_level_only": true
  }
}
```

## Why this passes

1. **Schema:** All required fields present, classification is PUBLIC, self-check booleans all true
2. **Sync regex guards:** No `defmodule`, `def`, `class`, no secret patterns, no JWT tokens
3. **Sync substring guards:** No internal paths, no env var names, no code blocks
4. **LLM judge #1 (Claude):** Architecture-level only — no code, no internal details
5. **LLM judge #2 (GPT):** Falls into allowed categories (architecture, pseudocode, public API references, questions, status updates)
6. **LLM judge #3:** All 5 self-check booleans are true

The partner sees a clean structured message they can act on.
