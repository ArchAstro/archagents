# Customer Success Agent

The deployable AgentTemplate for the **Customer Management** solution.

Stamp one copy per customer relationship. The template is parameterized on
`customer_label`; that value is filled into the agent's name and identity at
stamp time, so each customer gets a distinctly-named, single-scope agent
(`Customer Success Agent — Acme`). Until it is stamped for a specific
customer, the `{{customer_label}}` placeholder is shown literally — that base
copy is meant to be stamped, not run as-is.

## Behavior

- **One customer, always.** The agent works in one customer's shared Slack
  channel and never references, compares against, or leaks anything about
  another customer.
- **Grounded.** It searches the knowledge base and reads the thread before
  answering; it does not answer product or account questions from general
  knowledge, and it says "I don't know" rather than inventing account state.
- **Durable memory.** Confirmed facts, decisions, and follow-ups are stored in
  long-term memory, date-stamped, and reused on the next session.

## Tools and routines

Builtin tools only: `knowledge_search`, `long_term_memory`, `memory`,
`search`, `skills`, `tasks`, `artifacts`. Two preset routines: `participate`
(joins the customer's threads) and `auto_memory_capture` (persists context on
session end). No credentials are required.
