---
name: build-workflow
description: Use when the user wants to create, edit, or deploy a workflow — a multi-step process with branching, loops, HTTP calls, script execution, approvals, or scheduled routines. Trigger phrases include "build a workflow", "create a workflow", "design a workflow", "add a routine", "schedule a task", "automate this process", "set up a cron job", "workflow nodes".
allowed-tools: ["Bash(archagent:*)"]
---

# Build Workflow for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/cli/build-workflow.md`](../../../../shared/skills/cli/build-workflow.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
