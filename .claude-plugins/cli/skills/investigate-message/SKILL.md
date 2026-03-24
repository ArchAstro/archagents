---
name: investigate-message
description: Use when the user wants to investigate, debug, or troubleshoot a message in ArchAstro. Trigger phrases include "investigate message", "debug message", "look into a message", "find a message", "what happened with this message", "message issue", "message problem", "check message", "trace message", "message trajectory". Also use when the user describes a problem with a specific conversation, thread, or AI response.
---

# Investigate Message

Help the user find and investigate a specific message in ArchAstro, examine its metadata and trajectory, and work through debugging the issue.

## Phase 1: Gather Context

Ask the user questions to narrow down which message they're looking for. Use `AskUserQuestion` to make this interactive. You need to establish:

1. **Who sent the message?** Ask for the sender's name, email, or whether it was an AI/bot response.
2. **Which app?** Check the current default app with `archagent auth status`. If the user needs a different app, help them switch with `archagent settings set app <id>`.
3. **What thread or conversation?** Ask if they know the thread name, or if they can describe the conversation topic.
4. **When (approximately)?** Ask for a rough timeframe to help narrow results.
5. **What's the problem?** Understand what they're investigating - wrong AI response, missing message, unexpected behavior, etc.

Do NOT ask all questions at once. Start with the most important (who/what thread) and progressively narrow down.

## Phase 2: Find the Thread

Use the CLI to locate the thread:

```
archagent threads list
```

If there are many threads, help the user identify the right one by showing the list and asking them to confirm.

If the user mentioned a team, list teams first:
```
archagent teams list
```
Then describe the team to see its threads:
```
archagent teams describe <team-id>
```

If the user gave a sender email/name, find the user first:
```
archagent users list --search "<name or email>"
```

## Phase 3: Find the Message

Once you have the thread, list its messages:

```
archagent threads messages <thread-id>
```

Use `--page` to paginate through results if needed. Show the messages to the user and help them identify the right one based on content preview, sender, and timestamp.

If the user knows the sender, cross-reference the sender ID from the message list with:
```
archagent users describe <sender-id>
```

## Phase 4: Pull Message Details

Once the message is identified, get its full details:

```
archagent threads message <thread-id> <message-id>
```

This returns:
- **Content**: The full message text
- **Sender info**: Type (user/bot/system), sender ID, sender name
- **Attachments**: Files, artifacts, scraped links, media
- **Admin metadata**: Custom metadata object with debugging info
- **Trajectory**: The full chain of messages in the AI interaction
  - `trajectory.id` - Trajectory identifier
  - `trajectory.user_message_id` - The original user message that started this chain
  - `trajectory.agent_message_id` - The AI agent's response
  - `trajectory.messages` - All messages in the trajectory sequence

Present this information clearly to the user, organized by section.

## Phase 5: Analyze and Diagnose

Based on the message data, help the user understand what happened:

### For AI/bot response issues:
- Examine the **trajectory** to trace the full conversation chain
- Look at the **user_message_id** to see what prompt triggered the response
- Check the **metadata** for model info, token usage, tool calls, or error details
- If the trajectory has multiple messages, pull each one to reconstruct the full interaction:
  ```
  archagent threads message <thread-id> <each-message-id>
  ```

### For missing or unexpected messages:
- Check the thread message list for gaps in timestamps
- Look at sender types to identify if system messages intervened
- Check attachments for failed file uploads or broken links

### For configuration issues:
- Check the app's configs that may affect message handling:
  ```
  archagent configs list
  ```
- Look at relevant automations:
  ```
  archagent automations list
  ```
- Check personas if the AI personality seems wrong:
  ```
  archagent personas list
  ```

## Phase 6: Work with User to Fix

Based on the diagnosis, help the user fix the problem:

1. **Summarize findings**: Clearly explain what you found - what happened, why, and what the root cause appears to be.

2. **Suggest fixes**: Based on the issue type:
   - **Config issues**: Help update configs with `archagent configs update`
   - **Persona issues**: Help adjust persona settings with `archagent personas update`
   - **Automation issues**: Help modify automations with `archagent automations update`
   - **Code issues**: If the problem is in the codebase, help the user navigate to the relevant code and make fixes

3. **Verify the fix**: After making changes, help the user verify by checking the relevant resources again.

## Error Handling

- If `archagent` command is not found, or the installed version is older than `0.3.1`, tell the user to run `/cli:install`.
- If "Not authenticated" errors appear, tell the user to run `/cli:auth`.
- If "No app selected" errors appear, help them set one with `archagent settings set app <id>`.
- If API errors occur (404, 500), explain what the error means and suggest next steps.

## Important Notes

- Always use `--json` flag when you need to parse output programmatically.
- Be conversational and guide the user through the investigation step by step.
- Don't dump raw data - summarize and highlight the relevant parts.
- If the trajectory is long, focus on the key messages rather than showing everything.
