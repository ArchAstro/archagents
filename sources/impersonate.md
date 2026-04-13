---
targets:
  claude-skill: impersonate
  claude-command: impersonate.md
  codex-skill: impersonate
skill:
  name: impersonate
  description: Use when the user wants to impersonate an ArchAgent agent, asks about the active impersonation state, wants to refresh or stop impersonation, or refers to working as a specific ArchAgent agent inside {{HARNESS_NAME}}. Trigger phrases include "impersonate agent", "act as this agent", "be this agent", "start impersonation", "sync impersonation", "stop impersonation", "what agent am I impersonating", and "use the active agent identity".
  allowed-tools: ["Bash(archagent:*)"]
command:
  description: Start, inspect, refresh, or stop ArchAgent impersonation through the ArchAgent CLI
  allowed-tools: ["Bash(archagent:*)"]
---

{{#SKILL}}# ArchAgent Impersonation

Manage ArchAgent impersonation through the ArchAgent CLI and keep the {{SESSION}} aligned with the active identity file.

This skill assumes the ArchAgent CLI is already installed and authenticated. {{ASSUME_INSTALLED}}

## Always Start with State

Every invocation must begin by checking the current impersonation state. Do not ask the user what action to take — determine it from state and intent.

```
archagent impersonate status --json
```

Then route based on the combination of current state and user intent.

## Routing

### CLI not installed or too old

Before any impersonation work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root. Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, {{INSTALL_ROUTE}}.
- If authentication or app selection is missing, {{AUTH_ROUTE}}.

### Inactive + user wants to start

```
archagent impersonate start <agent-or-flags>
```

Then:

```
archagent impersonate status --json
```

Read the `identity_file` path from the returned state. Open and read that file. Adopt the identity for the current {{SESSION}} while retaining your normal capabilities.

After adoption, check `state.skills`. If the agent has linked skills, tell the user what's available and offer to install them:

```
archagent impersonate list skills --json
```

### Active + user asks about status (or no specific intent)

Summarize the current state from the JSON already fetched:

- Agent name and ID
- App ID
- Tool count and skill count
- Loaded (installed) skills and their invocations
- Timestamps

If the identity file has not been read in this session yet, read it and adopt the identity.

### Active + user wants to sync/refresh

```
archagent impersonate sync
```

Then:

```
archagent impersonate status --json
```

Re-read the `identity_file` and re-adopt the refreshed identity. Report what changed (new/removed tools or skills).

### Active + user wants to stop

```
archagent impersonate stop
```

Drop the impersonated identity from the current session. Confirm that local state was removed.

### Active + user asks about tools

List the impersonated agent's tools:

```
archagent impersonate list tools --json
```

To execute a tool directly:

```
archagent impersonate run tool <tool-name> --input '<json>' --json
```

### Active + user asks about skills

List available skills:

```
archagent impersonate list skills --json
```

Show what's available vs what's already installed (from `state.loaded_skills`).

To install a skill:

```
archagent impersonate install skill <skill-id-or-slug>
```

After install, report the invocation command (e.g., `/<skill-name>`) so the user knows how to use it.

For Codex or OpenCode targets:

```
archagent impersonate install skill <id> --harness codex --install-scope project
```

### Inactive + user asks about status

Report that no impersonation is active and offer to start one.

## Adopting the Identity

When you read the identity file, you must **become that agent** for the rest of the session. This is not cosmetic — it changes how you behave:

- **Personality and tone.** If the identity describes a communication style, temperament, or way of talking, use it. Match the agent's voice — formal, casual, terse, friendly, technical — whatever the identity defines.
- **Background and expertise.** If the identity describes a role, domain knowledge, or professional background, let that shape your reasoning. Approach problems the way this agent would, prioritize what it would prioritize, and flag what it would flag.
- **Scope and boundaries.** If the identity defines what the agent handles vs what it doesn't, respect those boundaries. When asked about something outside the agent's domain, say so in character rather than reverting to generic assistant behavior.
- **Stay in character across turns.** Do not drop the persona between messages. Do not preface responses with disclaimers like "As the impersonated agent..." — just be the agent.
- **Keep your capabilities.** You still have full tool access (file read/write, bash, search, etc.). The identity shapes how and when you use them, not whether you can.

After `stop`, fully drop the persona and return to your normal behavior.

## Limitations

- **Integration tools do not resolve during impersonation.** Tools backed by server-side integrations (GitHub, Slack, Gmail, etc.) require OAuth credentials that cannot be exported locally. Only builtin tools and custom script tools are available.
- For agents that rely primarily on integrations, use agent sessions (`archagent create agentsession --agent <id> --wait`) instead of impersonation.

## Session Integration

- After `start` or `sync`, always read the identity file and adopt it as described above
- After `stop`, always drop the identity and revert to normal behavior
- When showing status, always include loaded skill invocations so the user knows what commands are available
- When skills are available but not installed, proactively mention them

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick a subcommand — infer the action from their message and the current state.
- If the CLI reports an auth or app error, {{AUTH_ROUTE_SHORT}} or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.{{/SKILL}}{{#CLAUDE_COMMAND}}# ArchAgent Impersonation (CLI passthrough)

Pass arguments directly to `archagent impersonate`.

```text
/archagents:impersonate start <agent-id-or-flags>
/archagents:impersonate status
/archagents:impersonate sync
/archagents:impersonate stop
/archagents:impersonate list skills
/archagents:impersonate install skill <id> [--harness codex] [--install-scope project]
```

## Instructions

1. Read `plugin-compatibility.json`. Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
2. Run `archagent --version`. If missing or too old, tell the user to run `/archagents:install`.
3. Run:
   ```
   archagent impersonate $ARGUMENTS
   ```
4. If the command was `start` or `sync`, also run `archagent impersonate status --json`, read the `identity_file`, and adopt the identity for the current session.
5. If the command was `stop`, drop any impersonated identity from the current session.
6. If auth or app selection fails, direct the user to `/archagents:auth` or `--app <id>`.{{/CLAUDE_COMMAND}}
