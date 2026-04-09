---
name: chat
description: Use when the user wants to send a message to an ArchAstro agent, ask an agent a question, view a thread conversation, check for agent responses, or interact with an agent. Trigger phrases include "send a message", "ask the agent", "what did the agent say", "show the conversation", "check the thread", "talk to the agent", "message the agent", "create a session".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Agent Chat

Send messages to agents and view their responses.

This skill assumes the ArchAgent CLI is already installed and authenticated. Install or upgrade `archagent` if missing, and run `archagent auth login` if not authenticated.

## Quick Reference

| Task | Command |
|------|---------|
| Ask agent a question | `archagent create agentsession --agent <id> --instructions "..." --wait` |
| Create a thread | `archagent create thread --title "..." --owner-type agent --owner-id <agent-id> --json` |
| Create a test user | `archagent create user --system-user --name "..." --json` |
| Add member to thread | `archagent create threadmember --thread <id> --user-id <id> --json` |
| Add agent to thread | `archagent create threadmember --thread <id> --agent-id <id> --json` |
| Send message (wait for reply) | `archagent create threadmessage --thread <id> --user-id <id> -c "..." --wait --json` |
| View conversation | `archagent list threadmessages --thread <id> --full` |
| List agent sessions | `archagent list agentsessions --agent <id> --json` |

Use `--help` on any command for full options.

## Always Start with State

Every invocation must begin by understanding the current context. Determine:

1. Does the user want a quick one-off question (use agent session) or an ongoing conversation (use thread)?
2. Do they have an existing session or thread, or need a new one?

## Two Interaction Models

### Agent Sessions (recommended for most use cases)

Direct 1:1 conversation with an agent. Use `--wait` to stream the response via SSE.

**One-shot question** — put the question in `--instructions` and use `--wait`:
```
archagent create agentsession --agent <agent-id> --instructions "What are the open issues?" --wait
```
The agent processes the instructions as its task. `--wait` streams updates until completion.

**Multi-turn conversation** — create session, send messages with `exec --wait`:
```
archagent create agentsession --agent <agent-id> --thread-id <thread-id> --instructions "Respond to messages"
archagent exec agentsession <session-id> -m "What are the open issues?" --wait
```
`exec --wait` blocks and streams the agent's response in real-time. Without `--wait`, exec returns immediately after sending.

### Threads (for multi-participant conversations)

Threads support multiple users and agents. Use when you need ongoing conversation context or multiple participants.

## Routing

### CLI not installed or too old

Before any chat work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.archagents.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, instruct the user to install or upgrade `archagent`.
- If authentication or app selection is missing, instruct the user to run `archagent auth login`.

### User wants to ask an agent a question

**Preferred: agent session with `--wait`**

```
archagent create agentsession --agent <agent-id> --instructions "<question>" --wait
```
This creates the session, processes the question, and streams the result — all in one command.

For longer timeouts:
```
archagent create agentsession --agent <agent-id> --instructions "<question>" --wait --timeout 300
```

**Alternative: exec with `--wait`**

If you need to send follow-up messages to an existing session:
```
archagent exec agentsession <session-id> -m "<question>" --wait
```

**Without `--wait`** (fire-and-forget):
```
archagent create agentsession --agent <agent-id> --instructions "<question>"
archagent describe agentsession <session-id> --follow
```
Use `describe --follow` to stream updates on a session created without `--wait`.

### User wants to send a thread message

1. **Determine the sender ID**: Get the user's ID from `archagent auth status`.

2. **Send the message and wait for the response**:
   ```
   archagent create threadmessage --thread <thread-id> --user-id <user-id> --content "..." \
     --wait --wait-timeout 300
   ```

3. **When the response arrives**, read the full content:
   ```
   archagent list threadmessages --thread <thread-id> --full
   ```

### User wants to view a conversation

```
archagent list threadmessages --thread <thread-id> --full
```
Always use `--full` — the default table view truncates content.

### User needs a new thread

**Agent-owned thread** (recommended when an agent should participate):

1. Create the thread owned by the agent:
   ```
   archagent create thread --title "..." --owner-type agent --owner-id <agent-id> --json
   ```

2. Create a test user (if needed) and add them to the thread:
   ```
   archagent create user --system-user --name "Test User" --json
   archagent create threadmember --thread <thread-id> --user-id <user-id> --json
   ```

3. Send a message and wait for the agent to respond:
   ```
   archagent create threadmessage --thread <thread-id> --user-id <user-id> -c "Hello" --wait --json
   ```

4. View the conversation:
   ```
   archagent list threadmessages --thread <thread-id> --full
   ```

**User-owned thread** (when a user starts the conversation):

1. Create the thread:
   ```
   archagent create thread --title "..." --user <user-id> --json
   ```

2. Add the agent:
   ```
   archagent create threadmember --thread <thread-id> --agent-id <agent-id> --json
   ```

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick a subcommand — infer the action from their message.
- If the CLI reports an auth or app error, run `archagent auth login` or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.
- **Prefer agent sessions over threads** for simple question/answer interactions.
- **Always use `--wait`** when the user expects to see the agent's response.
