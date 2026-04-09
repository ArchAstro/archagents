---
name: build-workflow
description: Use when the user wants to create, edit, or deploy a workflow — a multi-step process with branching, loops, HTTP calls, script execution, approvals, or scheduled routines. Trigger phrases include "build a workflow", "create a workflow", "design a workflow", "add a routine", "schedule a task", "automate this process", "set up a cron job", "workflow nodes".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Workflow Builder

Create, edit, and deploy workflows — multi-step processes that agents execute via routines.

This skill assumes the ArchAgent CLI is already installed and authenticated. Install or upgrade `archagent` if missing, and run `archagent auth login` if not authenticated.

## What is a Workflow?

A workflow is a directed graph of nodes that defines a multi-step process. Use the dedicated top-level workflow resource for authoring: `archagent list workflows`, `describe workflow`, `create workflow`, `update workflow`, `validate workflow`, and `describe workflowdocs`. Workflows are then attached to agent routines for execution.

## Always Start with State

Every invocation must begin by understanding the current context:

```
archagent auth status
archagent list agents
```

Determine:
- Which agent will run this workflow?
- Is this a new workflow or an update to an existing one?
- What trigger should start it? (schedule, webhook, manual, message event)

## Routing

### CLI not installed or too old

Before any workflow work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, instruct the user to install or upgrade `archagent`.
- If authentication or app selection is missing, instruct the user to run `archagent auth login`.

### Workflow commands not exposed in the current `archagent` build

The source tree has dedicated top-level workflow commands, but some `archagent` builds may not expose them yet. Verify first:

```
archagent list workflows
archagent describe workflowdocs
```

If those commands are unavailable, do not keep insisting on them. Fall back to the config-managed workflow path and explain that the dedicated workflow resource exists in source but is not wired into the current binary.

### User wants to create a new workflow

**Phase 1: Gather requirements**

Understand the workflow before writing any config:
- What triggers it? (cron schedule, webhook, message, manual)
- What are the steps? (in plain language)
- Are there branches or conditions?
- Does it need to call external APIs?
- Does it need to send emails, Slack messages, or other notifications?
- Does it loop over a collection?

**Discover available events** to understand what can trigger the workflow and what data the trigger provides:
```
archagent list events
```

Once the user picks an event type, show them the payload schema so they know what `$` contains in downstream scripts:
```
archagent describe event <event-name>
```

This returns the JSON schema and a sample payload. The payload fields are accessible via `$` in scripts (e.g., `$.thread_id`, `$.message.content`).

**Phase 2: Scaffold the workflow**

Use the top-level workflow commands, not `describe configsample`/`validate config`, for the normal authoring loop when the current `archagent` build exposes them.

Create a workflow from a local JSON file:
```
archagent create workflow --id my-workflow --file ./workflows/my-workflow.json
```

Or let the CLI start from its built-in sample if you do not pass `--graph` or `--file`:
```
archagent create workflow --id my-workflow
```

**Phase 3: Author the workflow**

A workflow is a `WorkflowGraph` JSON config under the hood, but the user-facing authoring path should go through the top-level workflow commands.

A minimal workflow graph looks more like:
```json
{
  "kind": "WorkflowGraph",
  "version": 1,
  "name": "My Workflow",
  "start_node": "trigger_1",
  "nodes": [
    {
      "kind": "WorkflowTrigger",
      "id": "trigger_1",
      "trigger": "workflow.scheduled",
      "on_success": "script_1"
    },
    {
      "kind": "WorkflowScript",
      "id": "script_1",
      "script": "default-script"
    }
  ],
  "data": [
    {
      "kind": "Script",
      "id": "default-script",
      "script": "true"
    }
  ]
}
```

Use the live workflow docs when the graph shape is unclear:
```
archagent describe workflowdocs
```

If `workflowdocs` is not available in the current binary, say so explicitly and fall back to the config-managed path instead of pretending the command exists.

### Available node types

Do not hard-code a node taxonomy in this skill. The supported graph/node model is owned by the workflow implementation and `archagent describe workflowdocs`.

**Phase 4: Write supporting scripts**

If the workflow needs script logic, author and validate that script first. Route to the `build-script` skill for detailed script authoring guidance, or get the reference directly:
```
archagent describe scriptdocs
archagent describe configsample Script
```

**Phase 5: Validate**

Validate the workflow graph through the dedicated workflow command:
```
archagent validate workflow --file ./workflows/my-workflow.json
```

Validate any referenced scripts:
```
archagent validate script --file ./scripts/my-script.archscript
```

Fix any validation errors before deploying.

**Phase 6: Deploy**

Creating or updating the workflow through the top-level workflow commands persists it directly:
```
archagent create workflow --id my-workflow --file ./workflows/my-workflow.json
archagent update workflow my-workflow --file ./workflows/my-workflow.json
```

If the top-level workflow commands are unavailable in the current binary, or if the user is working inside a broader config-managed repo and explicitly wants that flow, route to `manage-configs` instead. Do not claim the dedicated workflow commands are available unless you verified them in the running CLI.

**Phase 7: Attach to a routine**

Workflows run via agent routines. Create or update a routine to use the workflow:

For a **scheduled** routine (cron):
```
archagent create agentroutine --agent <agent-id> \
  --name "Daily report" \
  --event-type schedule.cron \
  --schedule "0 9 * * 1-5" \
  --handler-type workflow_graph \
  --config-id <workflow-config-id>
```

For a **webhook-triggered** routine:
```
archagent create agentroutine --agent <agent-id> \
  --name "Inbound webhook handler" \
  --event-type webhook.inbound \
  --handler-type workflow_graph \
  --config-id <workflow-config-id>
```

To update an existing routine to use a workflow:
```
archagent update agentroutine <routine-id> \
  --handler-type workflow_graph \
  --config-id <workflow-config-id>
```

**Phase 8: Test and monitor**

Check routine runs:
```
archagent list agentroutineruns --routine <routine-id>
```

Use `println()` in scripts for debugging output.

### User wants to edit an existing workflow

1. **Inspect the current workflow**:
   ```
   archagent list workflows
   archagent describe workflow <id>
   ```

2. **Edit locally**, then validate and update:
   ```
   archagent validate workflow --file ./workflows/my-workflow.json
   archagent update workflow <id> --file ./workflows/my-workflow.json
   ```

   The workflow resource versions on update; the agent picks up the linked workflow config on the next run.

### User wants to set up a simple scheduled routine (no workflow)

Not everything needs a full workflow graph. For simple scheduled tasks, a routine can use a script directly.

**Reference a script resource** (preferred for production):
```
archagent create script --id daily-check --file ./scripts/daily-check.agentscript
archagent create agentroutine --agent <agent-id> \
  --name "Daily check" \
  --event-type schedule.cron \
  --schedule "0 9 * * 1-5" \
  --handler-type script \
  --config-id <script-config-id>
```
Get the config ID from `archagent describe script daily-check --output json` (the `configId` field).

**Or inline for quick prototyping:**
```
archagent create agentroutine --agent <agent-id> \
  --name "Daily check" \
  --event-type schedule.cron \
  --schedule "0 9 * * 1-5" \
  --handler-type script \
  --script 'println("hello")'
```

Or include the routine in the AgentTemplate:
```yaml
routines:
  - name: daily-check
    event_type: schedule.cron
    schedule: "0 9 * * 1-5"
    handler_type: script
    config_ref: daily-check-script
```

**Important**: Scheduled routines need both `schedule` and `event_type: schedule.cron`. Do not put schedules under nested `event_config.schedule`.

## Workflow Design Best Practices

- **Start simple**: Begin with a linear flow, add branching only when needed.
- **Name nodes clearly**: Use descriptive IDs (`fetch_orders`, `check_status`) not generic ones (`step1`, `step2`).
- **Handle errors**: Follow the real graph schema from `workflowdocs` and the sample config. Don't assume every HTTP call succeeds.
- **Use scripts for logic**: Keep business logic in Script resources or embedded workflow script data instead of improvising unsupported fields.
- **Test scripts independently**: Use `archagent run script --file <path>` to test scripts before wiring them into a workflow.
- **Cron syntax**: Standard 5-field cron. Use https://crontab.guru for help.

## Recovery Rules

- If workflow validation fails, show the exact error — it usually points to a specific node or field.
- If a routine run fails, check `archagent list agentroutineruns` for the error details.
- If a workflow depends on script logic that does not exist yet, create and validate that script first.
- If the user is unsure about workflow vs. simple routine, ask how many steps the process has. One step = simple routine. Multiple steps with branching = workflow.

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick raw subcommands when intent is clear.
- Keep responses concise and operational.
- When authoring workflows, show the user a concrete JSON graph draft they can review.
- Prefer showing the full workflow structure over explaining node types abstractly.
