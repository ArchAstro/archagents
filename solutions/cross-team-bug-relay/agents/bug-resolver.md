# Bug Resolver

Owning-side specialist for the cross-team bug relay. It runs the relay's
**Triage** stage: reproduce the defect a partner team reported, classify
the resolution, and write guidance the partner can act on without a
meeting.

## Resolution classes

| Resolution | Meaning | What the relay does next |
| --- | --- | --- |
| `attempt_workaround` | Partner can work around it now | Reporter applies the guidance and records the outcome |
| `provider_fix` | Owning team will fix it | Relay reports manual follow-up |
| `wont_fix` | Working as intended | Relay reports manual follow-up |
| `needs_more_info` | Not reproducible as reported | Relay reports manual follow-up with what's missing |

## Vendor-agnostic by design

The template ships with builtin tools only. Connect the owning product's
tools (API tooling, MCP servers, integrations) at install time; the
agent reports honestly when it cannot reproduce with what it has —
it never claims a check it did not perform.
