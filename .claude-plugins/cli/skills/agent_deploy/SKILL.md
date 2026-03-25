---
name: agent_deploy
description: Use when the user wants to deploy an ArchAstro agent, turn a config-driven agent repo into a running agent, or get an existing agent running in a thread. Trigger phrases include "deploy agent", "deploy this agent", "set up an agent", "launch agent", "ship this agent", "get this agent running".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Agent Deployment

Deploy an agent from a YAML template and get it running in a thread.

This skill depends on the `cli` plugin for CLI installation and authentication. Use that plugin's commands instead of trying to install or authenticate the CLI manually inside this skill.

## Always Start with State

Every invocation must begin by understanding what already exists:

```
archagent auth status
archagent list agents
```

If the user is working from a local repo, also inspect whether a `configs/` directory already exists. Determine whether they want to:
- deploy a new config-driven agent,
- redeploy an existing template,
- or work with an existing running agent.

## Routing

### CLI not installed or too old

Before any deployment work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.cli.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, direct the user to `/cli:install`.
- If authentication or app selection is missing, direct the user to `/cli:auth`.

### Local config directory not initialized

If the user has config files but no `configs/` directory set up, route to the `local_configs` skill first. That skill owns local config management.

### User wants to deploy a new agent

Use the config-driven golden path. Do not skip straight to `create agent`.

1. **Deploy configs first**:
   ```
   archagent configs deploy
   ```
   This pushes Script and AgentTemplate configs to the server. For config-driven agents, this should happen before provisioning the agent itself.

2. **Deploy the agent from the template file**:
   ```
   archagent deploy agent <yaml-file>
   ```
   This creates the full agent stack in one step: app config, agent record, routines, and installations. Note the agent ID (`agi_...`) from the output.

   **Important:** Always use `deploy agent`, not `create agent`. The `create agent` command only creates the agent record without provisioning routines or installations.

3. **Verify the deployment**:
   ```
   archagent list agents
   ```

4. **Offer next steps**: ask if the user wants to add the agent to a thread and start chatting. If yes, create a thread with members and hand off to the `chat` skill.

### User needs help creating or editing the config files first

Route to the `agent_authoring` skill before deploying. That skill owns:
- `AgentTemplate` and Script config creation
- `archagent configs sample`
- `archagent describe scriptdocs`
- routine scheduling shape
- env-var scope guidance

### User wants to add an agent to a thread

1. **If no thread exists**, create one:
   ```
   archagent create thread --title "..." --user <user-id>
   ```

2. **Add the agent as a member**:
   ```
   archagent create threadmember --thread <thread-id> --agent-id <agent-id>
   ```

3. **Add any other participants**:
   ```
   archagent create threadmember --thread <thread-id> --user-id <user-id>
   ```

4. **Confirm** the thread is ready and offer to send the first message.

### User asks about existing agents

List agents and present them:
```
archagent list agents
```

Summarize what's deployed and offer to deploy a new one or add an existing one to a thread.

## Recovery Rules

- If `archagent deploy agent` fails with a validation-style error, inspect the exact CLI output first. Do not immediately fall back to lower-level provisioning commands.
- If the problem appears to be in the config files, route to `agent_authoring`.
- If a script-related validation error appears, use:
  ```
  archagent describe scriptdocs
  archagent configs sample Script
  ```
  Do not invent script syntax from memory.
- Prefer human-readable `config_ref` names that match deployed config lookup keys. Do not rewrite refs to raw `cfg_...` IDs unless explicitly debugging a broken environment.

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick a subcommand — infer the action from their message.
- If the CLI reports an auth or app error, route to `/cli:auth` or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.
