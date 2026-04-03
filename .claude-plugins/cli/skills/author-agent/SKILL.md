---
name: author-agent
description: Use when the user wants to create or edit an ArchAstro agent's config files before deployment, including AgentTemplate files, Script configs, custom tools, routines, and environment setup. Trigger phrases include "build this agent", "write the template", "create the scripts", "set up the routines", "author this agent config".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Agent Authoring

Create or update the config files for a config-driven ArchAstro agent before deployment.

This skill depends on the `cli` plugin for CLI installation and authentication. Use that plugin's commands instead of trying to install or authenticate the CLI manually inside this skill.

## Always Start with State

Every invocation must begin by understanding the current project state:

```
archagent auth status
```

If the user is in a repo, inspect whether a `configs/` directory already exists and whether the agent already has Script or AgentTemplate files.

## Routing

### CLI not installed or too old

Before any authoring work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.cli.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, direct the user to `/cli:install`.
- If authentication or app selection is missing, direct the user to `/cli:auth`.

### Local config directory not initialized

If the user doesn't have a `configs/` directory set up yet, route to the `manage-configs` skill first. That skill owns `archagent init --enable-configs`, local file layout, and the sync/deploy workflow.

### User wants to author or modify agent configs

1. **Start from CLI-backed templates, not memory**:
   - For new config objects, use:
     ```
     archagent describe configsample <Kind>
     ```
   - For Script configs, always use:
     ```
     archagent describe scriptdocs
     archagent describe configsample Script
     ```
     The script docs are the live source of truth. Do not invent or paraphrase the language from memory.

2. **Use the standard config-driven model**:
   - Script logic lives in `kind: Script` configs.
   - Agent behavior lives in an `AgentTemplate`.
   - Custom tools should use `kind: custom`, `handler_type: script`, and `config_ref` pointing at Script configs.
   - When creating configs outside a project directory, use `-f` to read from a file:
     ```
     archagent create config -k AgentTemplate -f configs/agents/my-agent.yaml
     ```

3. **Validate early**:
   ```
   archagent validate config -k <Kind> -f <path>
   ```
   Run validation before deploy whenever the user changes Script or template files.

4. **Deploy through the normal flow after authoring**:
   - If the agent has Script configs or other supporting files, sync them first:
     ```
     archagent deploy configs
     ```
     This pushes local config files (Scripts, templates) but does not create agents.
     Skip this step if the agent only has a single AgentTemplate file — `deploy agent` handles its own config upload.
   - Then provision the agent from its template:
     ```
     archagent deploy agent <yaml-file>
     ```
     This uploads the template config and creates the agent with its routines, tools, and installations.
   - **Important:** `deploy configs` and `deploy agent` are different commands.
     Use `deploy configs` to sync a directory of config files; use `deploy agent` to create an agent from a template.

## Authoring Rules

### Script configs

- **Load the `build_script` skill for detailed script authoring guidance**, including syntax examples, common mistakes, and the validation/test/deploy workflow.
- Treat the script language as a functional expression language, not a general-purpose imperative language.
- Use `archagent describe scriptdocs` for exact syntax and available namespaces.
- If a script fails validation, prefer rewriting toward the sample/reference instead of trial-and-error improvisation.

### Routine configs inside templates

- Scheduled routines need both:
  - `schedule: "<cron>"`
  - `event_type: schedule.cron`
- Do not put schedules under nested `event_config.schedule`.
- To discover valid event types and their payload schemas:
  ```
  archagent list events
  archagent describe event <event-name>
  ```
  The payload schema from `describe event` shows what `$` contains in the routine's script handler.

### Config references

- Prefer human-readable `config_ref` values that match deployed config lookup keys.
- Do not convert refs to raw `cfg_...` IDs unless explicitly debugging a broken environment.

### Environment variables

- For org users, prefer org-scoped environment variables when they are sufficient for the agent's needs.
- Do not default users into app-scoped env-var flows unless the use case truly requires app scope.

## Recovery Rules

- If the user asks for a brand-new Script and the language shape is unclear, run `archagent describe scriptdocs` before drafting.
- If validation fails, surface the exact failing field or syntax problem. Do not immediately switch to lower-level provisioning commands.
- If the user asks to "just create the agent" while configs are still incomplete, finish authoring and validation first, then route to `deploy-agent`.

## Command Conventions

- All config commands are **verb-first**: `archagent list configs`, `archagent create config`, `archagent deploy configs`, `archagent sync configs`, `archagent validate config`, etc.
- There is no `archagent configs` namespace. Do not use `archagent configs <verb>` — always put the verb first.

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick raw subcommands when intent is clear.
- Keep responses concise and operational.
- Prefer the golden path over fallback commands.
