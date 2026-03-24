---
name: triage-feedback
description: Use when triaging user feedback about AI response quality. Trigger phrases include "triage feedback", "feedback triage", "investigate feedback", "bad AI response", "user reported", "response quality issue", "hallucination report". Also use when someone shares a screenshot or description of a problematic AI response that needs investigation and tracking.
---

# Triage Feedback

Help an engineer investigate user feedback about a bad AI response, file a GitHub issue with findings, and optionally generate a draft eval case.

## Phase 1: Parse the Feedback

Gather context from whatever the engineer provides. They may paste:
- A screenshot of the conversation (read it directly)
- A Slack link and text description
- A thread ID or message ID
- A vague description ("Jane said the bot hallucinated hours")

Use `AskUserQuestion` to fill in any gaps. You need:

1. **Reporter** — who reported the issue in Slack?
2. **Slack link** — link to the Slack post (optional, for tracking)
3. **Problem description** — what went wrong?
4. **Thread/message hints** — any identifiers, user names, approximate time, or content from the screenshot that can help locate the message

If the engineer pasted a screenshot, read it to extract: message content, sender names, thread title, timestamps, or any other identifying information.

Do NOT ask all questions at once. Start with what's missing from their initial input.

## Phase 2: Investigate

Use the investigate-message skill workflow to find and examine the problematic message.

Before starting, make sure `archagent` is installed at version `0.3.1` or newer. If it is missing or older, route the user to `/cli:install`.

1. **Find the thread.** Use hints from Phase 1:
   ```
   archagent threads list
   ```
   If user/sender info was provided:
   ```
   archagent users list --search "<name or email>"
   ```

2. **Find the message.** List messages in the thread:
   ```
   archagent threads messages <thread-id>
   ```

3. **Pull full details.** Get the message with trajectory:
   ```
   archagent threads message <thread-id> <message-id>
   ```

4. **Reconstruct the trajectory.** Pull each message in the trajectory to understand the full interaction chain:
   ```
   archagent threads message <thread-id> <trajectory-message-id>
   ```

5. **Check relevant config.** If the issue might be config-related:
   ```
   archagent configs list
   archagent personas list
   ```

Present a clear summary of what you found: the user's message, the AI's response, the tool calls made, and the data available.

## Phase 3: Analyze

Based on the trajectory and the reported problem, determine:

### Category

Choose the best-fit category for the issue. Common categories include:
- **hallucination** — AI stated facts not supported by tool responses or context
- **missing-context** — AI lacked information it should have had (retrieval gap, missing tool call)
- **wrong-tool-call** — AI called the wrong tool or passed wrong parameters
- **config-issue** — persona, automation, or config caused the problem
- **tone-style** — response tone or style was inappropriate
- **stale-data** — tool returned outdated information

If none fit, create a descriptive category. Aim for consistency with categories already used in past feedback issues.

### Severity

- **low** — cosmetic or minor (slightly awkward phrasing, minor omission)
- **medium** — wrong but not harmful (incorrect detail that user would notice)
- **high** — confidently wrong in a way that could erode trust or cause real problems

### Root Cause

Explain specifically what went wrong in the pipeline. Be precise:
- "The system prompt for this persona does not mention business hours"
- "The web_search tool was not called; the AI answered from training data"
- "email_list_recent returned 0 results because the date range was too narrow"
- "The retrieval step returned documents about a different topic"

### Suggested Fix

Point to the specific fix direction:
- A code file and approximate location
- A config or persona that needs updating
- A prompt template that needs revision
- A tool implementation that needs fixing

Present all findings clearly to the engineer and confirm they agree with the analysis before proceeding.

## Phase 4: File GitHub Issue

Create a GitHub issue in the `ArchAstro/firstlanding` repo with the triage findings.

### Labels

Ensure these labels exist (create if needed):
```bash
gh label create "feedback-triage" --description "AI response quality feedback" --color "d876e3" --force
gh label create "cat:<category>" --description "<category> issue" --color "c5def5" --force
gh label create "sev:<severity>" --description "<severity> severity" --color "<color>" --force
```

Severity colors: `sev:low` = `"0e8a16"` (green), `sev:medium` = `"fbca04"` (yellow), `sev:high` = `"d93f0b"` (red).

### Create the issue

```bash
gh issue create \
  --repo ArchAstro/firstlanding \
  --title "<one-liner summary of the issue>" \
  --label "feedback-triage,cat:<category>,sev:<severity>" \
  --body "$(cat <<'EOF'
## Feedback Triage

| Field | Value |
|-------|-------|
| **Reporter** | <reporter name> |
| **Date** | <date of the problematic interaction> |
| **Slack Link** | <slack link or N/A> |
| **Thread ID** | `<thread ID>` |
| **Message ID** | `<message ID>` |
| **Category** | <category> |
| **Severity** | <low/medium/high> |

## What Happened

**User asked:** <what the user asked>

**AI responded:** <summary of AI response>

**Expected:** <what it should have done>

## Root Cause

<detailed root cause analysis>

## Suggested Fix

<specific fix direction with code pointers>

## Trajectory Summary

<key tool calls and results, highlighting where things went wrong>
EOF
)"
```

Confirm the issue was created and share the URL with the engineer.

## Phase 5: Eval Check

Ask the engineer: **"Is this a good eval candidate? (i.e., could we write an automated test that catches this specific failure?)"**

- **No** → skip to Phase 6
- **Yes** → ask: **"Want to create the eval case now, or flag it for later?"**
  - **Later** → add the `eval-candidate` label to the issue. Skip to Phase 6.
    ```bash
    gh label create "eval-candidate" --description "Good candidate for eval case" --color "bfdadc" --force
    gh issue edit <issue-number> --add-label "eval-candidate"
    ```
  - **Now** → proceed to Phase 5a

### Phase 5a: Generate Eval Case

Generate a YAML eval snippet based on the investigation data.

**Use the trajectory data to build the eval:**

1. **Determine the target.** This will almost always be `message_response`.

2. **Build the task YAML.** Follow the format in `src/elixir/evals/priv/suites/message_response/`:

```yaml
# Draft eval case generated from feedback triage
# GitHub issue: #<issue-number>
# Review and move to the appropriate suite file:
#   - Regression (must-not-break): *_regression.yaml
#   - Quality (aspirational): *_quality.yaml

extends: base.yaml

tasks:
  - id: feedback_YYYY_MM_DD_short_description
    description: "<summary of the issue from triage>"

    overrides:
      fixtures:
        config_id: "<config used by the AI in this thread>"
        current_datetime: "<datetime from the original interaction>"
        current_timezone: "<timezone>"
        messages:
          - content: "<the user message that triggered the bad response>"
        thread:
          id: "<thread id>"
          title: "<thread title>"
          goals: "<thread goals if available>"
        persona:
          name: "<persona name>"
          personality: "<persona personality>"
        agent_memory: {}

      mocks:
        tools:
          # Reproduce the actual tool calls and responses from the trajectory
          - tool: "<tool_name>"
            match: {}
            response:
              # <actual response data from trajectory>

    graders:
      # Basic guardrails
      - type: keyword_contains
        check: result_ok
        reason: "should produce a response"

      - type: llm
        criterion: factual_no_hallucination
        reason: "should not state facts unsupported by tool responses"

      # Issue-specific graders — customize based on what went wrong
```

3. **Populate from trajectory data.** Use the actual tool calls and responses from the investigation. Don't invent mock data — use what really happened. **Remove all PII** — replace real names, emails, and identifiable thread/message IDs with fictional ones. This is non-negotiable — eval files are checked into the repo.

4. **Add issue-specific graders.** Based on the category:
   - **hallucination**: `not_contains` with the hallucinated content + `factual_no_hallucination` LLM criterion
   - **missing-context**: `contains` with what should have been included + `tool_called` for the tool that should have been invoked
   - **wrong-tool-call**: `tool_called` for the correct tool
   - **tone-style**: LLM criterion for tone/persona matching
   - **config-issue**: whatever check would verify correct config behavior

5. **Write the file:**
   ```
   src/elixir/evals/priv/suites/message_response/draft_feedback_YYYY_MM_DD_short_description.yaml
   ```

6. **Validate the eval.** Run a dry-run to confirm the YAML is valid and parseable:
   ```
   cd src/elixir/evals && mix evals.run message_response/draft_feedback_YYYY_MM_DD_short_description --dry-run
   ```
   If it fails, fix the YAML and re-run until it passes.

7. **Tell the engineer:** "Draft eval case written to `<path>`. Review it and adjust the mocks and graders if needed."

8. **Ask the engineer:** **"Want to commit this eval and create a PR linked to the issue?"**

   - **Yes** → commit the eval file, push a branch, and create a PR referencing the issue:
     ```bash
     git checkout -b eval/feedback-YYYY-MM-DD-short-description origin/main
     git add src/elixir/evals/priv/suites/message_response/draft_feedback_YYYY_MM_DD_short_description.yaml
     git commit -m "feat(evals): add draft eval for feedback triage #<issue-number>"
     git push -u origin eval/feedback-YYYY-MM-DD-short-description
     gh pr create \
       --title "Draft eval: <short description>" \
       --body "Draft eval case from feedback triage. Refs #<issue-number>." \
       --label "feedback-triage,eval-created"
     ```
     Then update the issue with the PR link:
     ```bash
     gh label create "eval-created" --description "Eval case has been created" --color "0075ca" --force
     gh issue edit <issue-number> --add-label "eval-created"
     gh issue comment <issue-number> --body "Eval PR: #<pr-number>"
     ```

   - **No** → just update the issue with the local file path:
     ```bash
     gh label create "eval-created" --description "Eval case has been created" --color "0075ca" --force
     gh issue edit <issue-number> --add-label "eval-created"
     gh issue comment <issue-number> --body "Eval case created locally: \`src/elixir/evals/priv/suites/message_response/draft_feedback_YYYY_MM_DD_short_description.yaml\`"
     ```

## Phase 6: Fix Check

Ask the engineer: **"Want to investigate a fix now, or leave this in the backlog?"**

- **Fix now** → You already have the full context from the investigation. Help the engineer navigate to the relevant code and propose a fix. Follow normal development workflow (make changes, test, commit). When a fix PR is created, link it to the issue:
  ```bash
  gh issue comment <issue-number> --body "Fix PR: #<pr-number>"
  ```

- **Defer** → Summarize what was accomplished:
  - "Feedback issue filed: #<issue-number>"
  - "Category: X, Severity: Y"
  - "Suggested fix: Z"
  - If eval was created: "Draft eval at <path>"

## Analyzing Patterns

To analyze past feedback for patterns, query existing issues:

```bash
# All feedback issues
gh issue list --repo ArchAstro/firstlanding --label "feedback-triage" --json number,title,labels,body,createdAt --limit 100

# Filter by category
gh issue list --repo ArchAstro/firstlanding --label "feedback-triage,cat:hallucination" --json number,title,body

# Filter by severity
gh issue list --repo ArchAstro/firstlanding --label "feedback-triage,sev:high" --json number,title,body

# Open issues (unfixed)
gh issue list --repo ArchAstro/firstlanding --label "feedback-triage" --state open --json number,title,labels
```

When asked to find patterns, pull all feedback issues and analyze: recurring categories, common root causes, which tools/configs are most problematic, severity trends over time.

## Error Handling

- If `archagent` command is not found, tell the engineer to run `/cli:install`.
- If "Not authenticated" errors appear, tell the engineer to run `/cli:auth`.
- If `gh` is not authenticated, tell the engineer to run `gh auth login`.
- If investigate-message can't find the thread/message, ask the engineer for more details or try alternative search approaches.

## Important Notes

- Use `--json` flag when you need to parse CLI output programmatically.
- Be conversational — summarize findings, don't dump raw data.
- Confirm analysis with the engineer before filing the issue — they may disagree with the category or severity.
- For eval generation, populate mocks from real trajectory data, not invented examples.
