# ArchAstro Onboarding

Walks a new ArchAstro user through deploying their first agent.
Fetches docs from `docs.archagents.com`, drives a step-by-step setup
conversation in a backing thread, and ships the support skills the
agent loads on demand (concepts, docs map, integration patterns, CLI
auth/install/config, script/workflow/skill authoring, deploy
guidance, chat testing, embed, and troubleshooting).

> **Provisioned by the app, not by `archagent install` alone.** The
> production onboarding agent is created by the app's onboarding flow
> via `createAgentAction` with template ref `default-agent`. That
> action provisions the backing thread, adds the onboarding agent as
> a member, and stores `thread_id` in `metadata`. `updateAgentAction`
> merges metadata, so updates preserve existing keys like
> `thread_id`. Use the Local Sample Install below to validate the
> agent config outside of that flow.

## How it triggers

Triggered by user messages in the backing thread that the
`createAgentAction` flow provisions. The agent does not run on a
cron and is not invoked by a webhook.

## Agent Contract

- **Name:** ArchAstro Onboarding
- **Description:** Guides a new user through setting up their first agent in ArchAstro.
- **Metadata:** `system_role: "archastro_onboarding"` and `onboarding_version: 1`
- **Template ref:** `default-agent` when created through `createAgentAction`
- **Thread:** provisioned by `createAgentAction`, then stored as `metadata.thread_id`

## Behavior

The onboarding agent helps the user clarify the job their first agent
should own, identify useful docs and files, and move quickly toward
testing. It directs users to:

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

This local sample deploys the agent config for validation and iteration.
The app runtime should still create the production onboarding agent through
`createAgentAction` so the backing thread and merged metadata are handled by the
product flow.
