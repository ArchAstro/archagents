---
name: chat
description: Use when the user wants to send a message to an ArchAstro agent, view a thread conversation, check for agent responses, or interact with an agent in a thread. Trigger phrases include "send a message", "ask the agent", "what did the agent say", "show the conversation", "check the thread", "talk to the agent", "message the agent".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Agent Chat

Send messages to agents in threads and view their responses.

This skill depends on the `cli` plugin for CLI installation and authentication. Use that plugin's commands instead of trying to install or authenticate the CLI manually inside this skill.

## Always Start with State

Every invocation must begin by understanding the current context. Determine:

1. Does the user have a thread in mind, or do they need one created?
2. Are they sending a new message, or checking for responses?

## Routing

### CLI not installed or too old

Before any chat work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.cli.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, direct the user to `/cli:install`.
- If authentication or app selection is missing, direct the user to `/cli:auth`.

### User wants to send a message

1. **Determine the sender ID**:

   **Org mode** (authenticated as an app user): Get the user's ID from `archagent auth status`.

   **Developer mode** (authenticated as a developer): Look up thread members:
   ```
   archagent list threadmembers --thread <thread-id>
   ```

2. **Send the message and wait for the response**:
   ```
   archagent create threadmessage --thread <thread-id> --user-id <user-id> --content "..." \
     --wait --wait-timeout 300
   ```
   Use `run_in_background: true` so you remain responsive while waiting.

   - `--wait-settle 5` (default) waits 5 seconds after the last message before returning, in case the agent sends multiple messages.
   - Set `--wait-timeout` generously — agent responses often take 30–90 seconds, sometimes longer.

3. **Tell the user** the message was sent and the agent is processing. Let them know you're available while waiting.

4. **When the response arrives**, read the full content:
   ```
   archagent list threadmessages --thread <thread-id> --full
   ```

5. **Present the response**: summarize key points, highlight action items or decisions, offer to send a follow-up.

### User wants to view a conversation

1. **Fetch messages with full content**:
   ```
   archagent list threadmessages --thread <thread-id> --full
   ```
   Always use `--full` — the default table view truncates content to 60 characters.

   For programmatic processing:
   ```
   archagent list threadmessages --thread <thread-id> --json
   ```

2. **Present the conversation**:
   - Summarize the overall flow (who said what, key decisions)
   - For each message, show the sender and a concise summary
   - Highlight agent feedback, action items, or decisions
   - Offer to expand any individual message on request

### User needs a new thread

1. **Create the thread**:
   ```
   archagent create thread --title "..." --user <user-id>
   ```
   The `--user` is the thread owner. Note the thread ID from the output.

2. **Add members** — agents and users who participate:
   ```
   archagent create threadmember --thread <thread-id> --agent-id <agent-id>
   archagent create threadmember --thread <thread-id> --user-id <user-id>
   ```
   A thread typically needs at least one agent and one user before messaging.

3. Once members are added, route to "User wants to send a message" if they have something to say.

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick a subcommand — infer the action from their message.
- If the CLI reports an auth or app error, route to `/cli:auth` or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.
