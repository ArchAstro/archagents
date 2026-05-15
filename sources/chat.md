---
targets:
  claude-skill: chat
  codex-skill: chat
skill:
  name: chat
  description: Use when the user wants to send a message to an ArchAstro agent, ask an agent a question, view a thread conversation, check for agent responses, or interact with an agent. Trigger phrases include "send a message", "ask the agent", "what did the agent say", "show the conversation", "check the thread", "talk to the agent", "message the agent", "create a session".
  allowed-tools: ["Bash(archagent:*)"]
---


# ArchAstro Agent Chat

Send messages to agents and view their responses.

This skill assumes the ArchAgent CLI is already installed and authenticated. {{ASSUME_INSTALLED}}

## Quick Reference

| Task | Command |
|------|---------|
| Ask agent a question | `archagent create agentsession --agent <id> --instructions "..." --wait` |
| Send follow-up to a session | `archagent exec agentsession <session-id> -m "..." --wait` |
| View a session | `archagent describe agentsession <session-id>` |
| Create a shared thread | `archagent create thread --title "..." --owner-type agent --owner-id <agent-id> --json` |
| Start a session in a thread | `archagent create agentsession --agent <id> --thread <thread-id> --instructions "..." --wait` |
| List agent sessions | `archagent list agentsessions --agent <id> --json` |
| Send a message into a thread and wait for replies | `echo '{"content":"..."}' \| archagent watch thread <thread-id> --idle-timeout 30` |
| Tail a thread for new messages (read-only) | `archagent watch thread <thread-id> --idle-timeout 60 < /dev/null` |

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

There are two ways to work inside a thread:

- **Agent session attached to the thread** (`create agentsession --thread <id>`) — best when you want a *specific* agent to take on a discrete task using thread context. The session has its own lifecycle and result.
- **Watch the thread directly** (`watch thread <id>`) — best when you (or your script) want to *participate as a thread member*: send your own messages and stream replies from every other member as they arrive. Use this when the conversation involves multiple bots, the human user is one of the participants, or you simply want to tail what's happening.

Default to the agent-session approach unless you specifically need bidirectional participation or to observe multi-agent activity live.

## Routing

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

### User wants to use a thread

Use a thread when the user explicitly needs shared context or multiple
participants. Start agent work with an agent session attached to the
thread instead of sending a raw thread message.

1. **Create or identify the thread**.

2. **Start an agent session in that thread**:
   ```
   archagent create agentsession --agent <agent-id> --thread <thread-id> \
     --instructions "..." --wait --timeout 300
   ```

3. **Send follow-ups through the session**:
   ```
   archagent exec agentsession <session-id> -m "..." --wait --timeout 300
   ```

### User wants to chat in a thread or tail one in real time

Use `archagent watch thread <thread-id>` when the user wants to send
ad-hoc messages into a thread and see replies from every member stream
back, or when they want to tail an active thread without committing to
an agent session.

**Send one message and wait for replies, then exit:**
```
echo '{"content":"<message>"}' | archagent watch thread <thread-id> --idle-timeout 30
```

**Have a multi-turn conversation from a script:**
```
{
  echo '{"content":"first question"}'
  sleep 20
  echo '{"content":"follow-up"}'
} | archagent watch thread <thread-id> --idle-timeout 30
```

**Tail read-only (no sending), including recent history:**
```
archagent watch thread <thread-id> --include-history --idle-timeout 120 < /dev/null
```

The verb reads one JSON record per line from stdin
(`{"content": "...", "reply_to"?: "<msg-id>", "idempotency_key"?: "..."}`)
and writes one JSON event per line to stdout:

- `{"type":"message","data":{...Message}}` — incoming message from any
  other member.
- `{"type":"sent","data":{...Message}}` — your own send (only when
  `--echo` is set).
- `{"type":"error","message":"...","input"?: <record>}` — an invalid
  input record or a send/poll failure.

Common flags: `--user <id>` / `--agent <id>` (sender identity, defaults
to the authenticated user in org mode), `--since <message-id>`,
`--include-history`, `--history-limit <n>`, `--idle-timeout <seconds>`
(0 = run forever), `--exit-on-eof` (exit when stdin closes),
`--echo`. Run `archagent watch thread --help` for the full list and the
exact input/output shapes.

**Foreground vs. background.** Short send-and-wait invocations (small
`--idle-timeout`) should stay in the foreground — they're synchronous
and the reply is what the user is waiting for. Long-running watches
(`--idle-timeout 0` or multi-minute tails) should be backgrounded so
you can keep working while messages stream in; check the watcher's
output periodically to surface new messages.

### User wants to view a conversation

For an agent session:
```
archagent describe agentsession <session-id>
```
Use `archagent list agentsessions --agent <agent-id> --json` if you
need to find the session first.

For a thread, use `watch thread <id> --include-history --idle-timeout
<seconds> < /dev/null` to dump recent messages and then stream any new
ones (see the "chat in a thread" section above).

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

3. Start a session in the thread and wait for the agent to respond:
   ```
   archagent create agentsession --agent <agent-id> --thread <thread-id> \
     --instructions "Hello" --wait --timeout 300
   ```

4. View the session:
   ```
   archagent describe agentsession <session-id>
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
- If the CLI reports an auth or app error, {{AUTH_ROUTE_SHORT}} or suggest `--app <id>`.
- Keep responses concise — state the outcome, not the process.
- **Prefer agent sessions over threads** for simple question/answer interactions.
- **Always use `--wait`** when the user expects to see the agent's response.
