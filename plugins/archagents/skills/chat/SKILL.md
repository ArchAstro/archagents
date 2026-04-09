---
name: chat
description: Use when the user wants to send a message to an ArchAstro agent, ask an agent a question, view a thread conversation, check for agent responses, or interact with an agent. Trigger phrases include "send a message", "ask the agent", "what did the agent say", "show the conversation", "check the thread", "talk to the agent", "message the agent", "create a session".
allowed-tools: ["Bash(archagent:*)"]
---

# Chat for Codex

Codex entrypoint for the shared workflow details.

Shared workflow details:

- [`shared/skills/archagents/chat.md`](../../../../shared/skills/archagents/chat.md)

Codex-specific notes:

- Keep routing and wording in Codex terms, not Claude slash commands.
- If the CLI is missing or too old, have the user install or upgrade `archagent` before continuing.
- If authentication or app selection is missing, have the user authenticate `archagent` before continuing.
