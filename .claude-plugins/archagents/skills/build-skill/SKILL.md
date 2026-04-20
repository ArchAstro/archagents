---
name: build-skill
description: Use when the user wants to create, edit, or publish an ArchAstro skill — a reusable package of instructions and supporting files that agents can use. Trigger phrases include "build a skill", "create a skill", "write a skill", "author a skill", "new skill", "skill template", "SKILL.md".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Skill Builder

Create, edit, and publish skills — reusable instruction packages that agents invoke at runtime.

This skill assumes the ArchAgent CLI is already installed and authenticated. Use the `/archagents:install` and `/archagents:auth` commands in this same plugin instead of trying to install or authenticate the CLI manually inside this skill.

## What is a Skill?

A skill is a file-backed bundle anchored by a `SKILL.md` root file with optional supporting files. Skills use the same managed virtual-path model as scripts and workflows: skills live under `skills/<slug>/...`, scripts under `scripts/...`, and workflows under `workflows/...`. Agents invoke skills at runtime via the `get_skill` tool to load instructions on demand.

## Always Start with State

Every invocation must begin by understanding the current context:

```
archagent auth status
archagent list skills
```

Determine whether the user wants to:
- create a brand-new skill,
- edit an existing skill,
- or inspect a skill before modifying it.

## Routing

### User wants to create a new skill

Walk through the authoring flow step by step.

1. **Gather requirements**:
   - What should the skill do? (purpose and scope)
   - What trigger phrases should activate it? (for the description field)
   - Does it need supporting files (templates, schemas, reference docs)?
   - Which agent(s) will use it?

2. **Choose a slug**: Short, lowercase, hyphen-separated identifier (e.g., `order-lookup`, `weekly-report`). This becomes the skill's permanent key.

3. **Author the SKILL.md file locally**:

   Create a directory structure:
   ```
   skills/<slug>/
   ├── SKILL.md              # Root file (required)
   └── references/            # Optional supporting files
       └── example.md
   ```

   The SKILL.md must have YAML frontmatter:
   ```yaml
   ---
   name: <skill-name>
   description: <One-line description with trigger phrases. Be specific — this is how
     the agent decides when to invoke the skill. Include phrases like "use when...",
     "trigger phrases include...">
   ---

   # Skill Title

   Detailed instructions for the agent...
   ```

4. **Write effective skill instructions**:
   - **Be concrete**: Provide exact CLI commands, API calls, or code patterns the agent should use.
   - **Use phases**: Break complex workflows into numbered phases with clear entry/exit criteria.
   - **Include routing**: Tell the agent how to handle different user intents within the skill's scope.
   - **Add recovery rules**: What to do when things fail.
   - **Set response rules**: How terse or verbose the agent should be.
   - **Keep it narrow**: One skill, one job. If it's doing two things, split into two skills.

5. **Publish the skill to the platform**:

   **Option A — Via `deploy configs`** (recommended when working with a configs/ directory):

   Place the skill directory under `configs/skills/<slug>/` and deploy:
   ```
   archagent deploy configs
   ```
   This automatically creates the skill with name and description from the SKILL.md frontmatter, and publishes all supporting files as File configs. See the `manage-configs` skill for setting up the configs directory.

   **Option B — Via dedicated commands:**
   ```
   archagent create skill -n "<Name>" -d "<Description>" -s <slug> --file ./skills/<slug>/SKILL.md
   ```

   If there are supporting files, add them:
   ```
   archagent create skillfile <slug> references/example.md --file ./skills/<slug>/references/example.md
   ```

6. **Verify the skill was created**:
   ```
   archagent describe skill <slug>
   archagent describe skillfile <slug> SKILL.md
   ```

7. **Link the skill to an agent**: Skills are linked to agents via the agent's tools configuration. The agent needs a `get_skill` tool or the skill needs to be included in the agent's skill list. If the user has an agent they want to link:
   ```
   archagent list agents
   ```
   Then update the agent's config to reference the skill.

### User wants to edit an existing skill

1. **Inspect the current state**:
   ```
   archagent describe skill <slug>
   archagent describe skillfile <slug> SKILL.md
   ```

2. **Make edits locally**, then update:
   ```
   archagent update skillfile <slug> SKILL.md --file ./skills/<slug>/SKILL.md
   ```

   For supporting files:
   ```
   archagent update skillfile <slug> <path> --file ./local/path
   ```

3. **Verify the update**:
   ```
   archagent describe skillfile <slug> SKILL.md
   ```

### User wants to install a skill into their local coding harness

Skills can be installed locally for use in Claude Code, Codex, or OpenCode:

```
archagent impersonate start <agent-id>
archagent impersonate list skills
archagent impersonate install skill <skill-config-id> --harness claude
archagent impersonate install skill <skill-config-id> --harness codex --install-scope project
archagent impersonate install skill <skill-config-id> --harness opencode
```

After installation, the skill appears in the local `.claude/skills/`, `.codex/skills/`, or `.opencode/skills/` directory.

## Skill Authoring Best Practices

- **Narrow scope**: Each skill should do one thing well. Split broad skills into composable pieces.
- **Concrete instructions**: Provide exact commands and patterns, not vague guidance.
- **Trigger phrases**: The description field is how agents route to the skill — make trigger phrases specific and varied.
- **Version awareness**: When updating a skill, keep in mind that running agents pick up changes on next invocation.
- **Review before publishing**: Skills are executable instructions — review them like code.
- **Supporting files**: Use `references/` subdirectories for large reference material the skill can load on demand.

## Recovery Rules

- If `archagent create skill` fails with a duplicate slug error, the skill already exists — offer to update it instead.
- If the user is unsure about the skill format, show them the SKILL.md template above.
- If the user asks for a "sample skill", generate one from the template with placeholder content tailored to their use case.

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not ask the user to pick raw subcommands when intent is clear.
- Keep responses concise and operational.
- Prefer showing the user a concrete SKILL.md draft they can review over abstract guidance.
