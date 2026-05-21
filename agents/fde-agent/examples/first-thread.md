# Example: FDE Agent Runs A First Thread

> **Customer**: We want an FDE agent for our support escalation workflow.
> Help me scope the first shippable version.

> **FDE Agent**: I will ground this in the configured project context first,
> then scope the smallest shippable version.

> **FDE Agent**: I need six details to lock the scope:
>
> 1. What support system owns the ticket?
> 2. What condition makes a ticket an escalation?
> 3. Who receives the escalation?
> 4. What context must be included?
> 5. What should the agent never do?
> 6. How will we know the first version worked?

> **Customer**: Zendesk owns tickets. Tier 2 escalation happens when an
> enterprise customer has a P1 or P2 ticket open for more than 30 minutes
> without owner response. The agent should summarize the ticket and post
> in Slack. It should never message the customer or change the ticket
> status. Success is a Slack alert with the right summary and link.

> **FDE Agent**: Confirming scope: first version watches Zendesk for
> enterprise P1/P2 tickets with no owner response after 30 minutes,
> summarizes the case, and posts a Slack escalation message with a ticket
> link. It will not message customers, change ticket status, assign
> owners, or close tickets. Success is a correct Slack alert for a real
> qualifying ticket.
>
> Thin slice:
>
> 1. Document Zendesk fields for priority, enterprise account, owner
>    response timestamp, and ticket URL.
> 2. Create a scheduled check or Zendesk webhook trigger.
> 3. Fetch candidate tickets.
> 4. Filter to enterprise P1/P2 tickets stale for 30 minutes.
> 5. Generate a short summary from ticket messages.
> 6. Post to the approved Slack channel.
> 7. Test with one known ticket and capture the result.
>
> Remaining blockers to resolve before implementation: Zendesk field names,
> approved Slack channel, and sample redacted tickets for validation.
