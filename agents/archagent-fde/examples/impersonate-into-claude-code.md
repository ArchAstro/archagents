# Example: Impersonate the FDE into Claude Code

The FDE agent is most powerful when you install its skill set into
your own coding harness. This turns Claude Code (or Codex, or
OpenCode) into an ArchAgents FDE that lives in your terminal.

## Steps

```bash
# 1. Start impersonation
archagent impersonate start archagent-fde

# 2. See which skills the FDE has
archagent impersonate list skills

# Output:
#   archagent-fde-engagement-playbook    End-to-end engagement playbook
#   archagent-concepts                    Canonical concept reference
#   archagent-docs-map                    Curated docs URL index
#   archagent-integration-patterns        Seven common integration shapes
#   archagent-troubleshooting             Debugging playbook
#   archagent-install, archagent-auth, archagent-manage-configs,
#   archagent-author-agent, archagent-build-script,
#   archagent-build-workflow, archagent-build-skill,
#   archagent-deploy-agent, archagent-chat, archagent-impersonate

# 3. Install the whole set into Claude Code
for id in $(archagent impersonate list skills --ids-only); do
  archagent impersonate install skill "$id" --harness claude
done

# 4. Restart Claude Code. The skills now appear under .claude/skills/
#    and are available to the user as /<skill-name> slash commands
#    and to the model as on-demand knowledge.
```

For Codex:

```bash
archagent impersonate install skill <id> --harness codex --install-scope project
```

For OpenCode:

```bash
archagent impersonate install skill <id> --harness opencode
```

## What changes

Before impersonation, Claude Code is a general coding agent. After,
it can:

- Guide you through an ArchAgents engagement phase by phase
  (`/archagent-fde-engagement-playbook`)
- Answer "what's the difference between a routine and an automation?"
  without hallucinating
- Produce `agent.yaml` snippets for all seven common integration
  patterns
- Diagnose broken routines with a real playbook, not a hunch
- Write, validate, and deploy `.aascript` files with CLI commands that
  actually exist
- Install skills into itself via the impersonate loop (yes, it can
  install more skills into itself)

## Stopping

```bash
archagent impersonate stop
```

Uninstall skills with `archagent impersonate uninstall skill <id>` if
you want to fully revert.
