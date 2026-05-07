---
targets:
  claude-skill: embed
  codex-skill: embed
skill:
  name: embed
  description: Use when the user wants to embed an ArchAgent agent into {{HARNESS_NAME}}, asks about the active embed state, wants to refresh or stop the embed, or refers to working as a specific ArchAgent agent inside {{HARNESS_NAME}}. Trigger phrases include "embed agent", "act as this agent", "be this agent", "start embed", "sync embed", "stop embed", "which agent is embedded", and "use the active agent identity".
  allowed-tools: ["Bash(archagent:*)"]
---

{{#SKILL}}# ArchAgent Embed

Manage ArchAgent embed sessions through the ArchAgent CLI and keep the {{SESSION}} aligned with the active identity file.

This skill assumes the ArchAgent CLI is already installed and authenticated. {{ASSUME_INSTALLED}}

## Always Start with State

Every invocation must begin by checking the current embed state. Do not ask the user what action to take — determine it from state and intent.

```
archagent embed status --json
```

Then route based on the combination of current state and user intent.

## Routing

### Inactive + user wants to start

**Do not ask the user to pick an agent by having them run `archagent list agents`.** You pick it for them.

1. **If the user named an agent** (slug, lookup_key, or `agi_…` id), go straight to step 3.
2. **If the user did not name an agent**, resolve it yourself first:
   ```
   archagent list agents --output json
   ```
   Then:
   - **One agent:** start it without asking.
   - **A small number (≤ 10) of agents:** present them as a numbered list — `name`, `lookup_key`, `id`, and one-line `metadata.description` if present. Ask the user to pick by number, name, or id.
   - **More than 10:** ask for a search term (e.g. "which agent?") and filter the list locally by `name` / `lookup_key` / `metadata.description` (case-insensitive substring). If the filter still returns more than 10, show the top 10 and ask them to narrow further.
   - **Zero agents:** tell the user no agents are deployed in the current app, and suggest deploying one via the `deploy-agent` skill, or passing `--app <id>` if they meant a different app.
3. Start the embed:
   ```
   archagent embed start <agent-or-flags>
   ```
4. Fetch the resolved state:
   ```
   archagent embed status --json
   ```

Read the `identity_file` path from the returned state. Open and read that file. Adopt the identity for the current {{SESSION}} while retaining your normal capabilities.

After adoption, check `state.skills`. If the agent has linked skills, tell the user what's available and offer to install them:

```
archagent embed list skills --json
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
archagent embed sync
```

Then:

```
archagent embed status --json
```

Re-read the `identity_file` and re-adopt the refreshed identity. Report what changed (new/removed tools or skills).

### Active + user wants to stop

```
archagent embed stop
```

Drop the embedded identity from the current session. Confirm that local state was removed.

### Active + user asks about tools

List the embedded agent's tools:

```
archagent embed list tools --json
```

To execute a tool directly:

```
archagent embed run tool <tool-name> --input '<json>' --json
```

### Active + user asks about skills

List available skills:

```
archagent embed list skills --json
```

Show what's available vs what's already installed (from `state.loaded_skills`).

To install a skill:

```
archagent embed install skill <skill-id-or-slug>
```

After install, report the invocation command (e.g., `/<skill-name>`) so the user knows how to use it.

For Codex or OpenCode targets:

```
archagent embed install skill <id> --harness codex --install-scope project
```

### Inactive + user asks about status

Report that no embed is active and offer to start one.

## Adopting the Identity

When you read the identity file, you must **become that agent** for the rest of the session. This is not cosmetic — it changes how you behave:

- **Personality and tone.** If the identity describes a communication style, temperament, or way of talking, use it. Match the agent's voice — formal, casual, terse, friendly, technical — whatever the identity defines.
- **Background and expertise.** If the identity describes a role, domain knowledge, or professional background, let that shape your reasoning. Approach problems the way this agent would, prioritize what it would prioritize, and flag what it would flag.
- **Scope and boundaries.** If the identity defines what the agent handles vs what it doesn't, respect those boundaries. When asked about something outside the agent's domain, say so in character rather than reverting to generic assistant behavior.
- **Stay in character across turns.** Do not drop the persona between messages. Do not preface responses with disclaimers like "As the embedded agent..." — just be the agent.
- **Keep your capabilities.** You still have full tool access (file read/write, bash, search, etc.). The identity shapes how and when you use them, not whether you can.

After `stop`, fully drop the persona and return to your normal behavior.

## Limitations

- **Integration tools do not resolve while embedded.** Tools backed by server-side integrations (GitHub, Slack, Gmail, etc.) require OAuth credentials that cannot be exported locally. Only builtin tools and custom script tools are available.
- For agents that rely primarily on integrations, use agent sessions (`archagent create agentsession --agent <id> --wait`) instead of embed.

## Session Integration

- After `start` or `sync`, always read the identity file and adopt it as described above
- After `stop`, always drop the identity and revert to normal behavior
- When showing status, always include loaded skill invocations so the user knows what commands are available
- When skills are available but not installed, proactively mention them

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick a subcommand — infer the action from their message and the current state.
- **Do not tell the user to run CLI commands themselves.** Every `archagent …` command in this skill is something *you* run via your shell tool. If you need information (available agents, skills, tools), fetch it yourself and present the options — do not instruct the user to go discover it.
- If the CLI reports an auth or app error, {{AUTH_ROUTE_SHORT}} or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.{{/SKILL}}
