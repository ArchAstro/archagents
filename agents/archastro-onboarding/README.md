# ArchAstro Onboarding

Guides a new user through setting up their first agent in ArchAstro.

This template is meant for the onboarding agent created by the app flow. In
production, create it through `createAgentAction` with the default template ref
`default-agent`; that action provisions the backing thread, adds the onboarding
agent as a member, and stores `thread_id` in metadata.

This sample also owns the ArchAgents onboarding support bundle: docs fetching,
concept explanations, integration patterns, CLI setup/auth/config workflows,
script/workflow/skill authoring, deploy guidance, chat testing, embed,
and troubleshooting.

## Agent Contract

- **Name:** ArchAstro Onboarding
- **Description:** Guides a new user through setting up their first agent in ArchAstro.
- **Metadata:** `system_role: "archastro_onboarding"` and `onboarding_version: 1`
- **Template ref:** `default-agent` when created through `createAgentAction`
- **Thread:** provisioned by `createAgentAction`, then stored as `metadata.thread_id`

`updateAgentAction` merges metadata, so updates should preserve existing keys
like `thread_id`.

## Behavior

The onboarding agent helps the user clarify the job their first agent should
own, identify useful docs/files/examples, and move quickly toward testing.

It must not invent user, company, customer, or technical context. It should not
pretend there is a hidden onboarding surface. It should direct users to:

- **Add context** for docs links and files
- **Chat with your agent** for testing

The exact identity and kickoff prompts are in [prompts.md](prompts.md).

## Support Bundle

The onboarding agent ships these skills:

- `archastro-engagement-playbook`
- `archagent-concepts`
- `archagent-docs-map`
- `archagent-integration-patterns`
- `archagent-troubleshooting`
- `archagent-install`
- `archagent-auth`
- `archagent-manage-configs`
- `archagent-author-agent`
- `archagent-build-script`
- `archagent-build-workflow`
- `archagent-build-skill`
- `archagent-deploy-agent`
- `archagent-chat`
- `archagent-embed`

It also ships `fetch_archagents_docs`, backed by
`scripts/archastro-fetch-archagents-docs.aascript`.

## Local Sample Install

```bash
archagent install agentsample archastro-onboarding
```

This local sample deploys the AgentTemplate shape for validation and iteration.
The app runtime should still create the production onboarding agent through
`createAgentAction` so the backing thread and merged metadata are handled by the
product flow.
