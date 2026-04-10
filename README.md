# ArchAgents

CLI, plugins, and production-ready sample agents for the ArchAgents platform.

## Sample Agents

Deploy a working agent in minutes. See [`agents/`](agents/) for the full list:

| Agent | What it does |
|---|---|
| [Code Review](agents/code-review-agent) | Reviews every PR with inline comments |
| [Compliance Reviewer](agents/compliance-reviewer) | Checks PRs against SOC2 / GDPR / custom rules |
| [Cross-Org Collab](agents/cross-org-collab-agent) | Privacy-by-construction field guards for cross-org threads |
| [Onboarding Q&A](agents/onboarding-qa) | Answers new-hire questions from your knowledge base |
| [Release Notes](agents/release-notes-bot) | Weekly changelog from merged PRs |
| [Security Triage](agents/security-triage-agent) | Daily dep scan, auto-fix CVEs, escalate the rest |
| [Threat Intel](agents/threat-intel-agent) | Daily security brief from HN + GitHub Advisories |

## Install

GitHub Releases are the canonical distribution path.

### macOS

Prefer Homebrew when available:

```bash
brew install ArchAstro/tools/archagent
```

Fallback to the installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
```

### Linux

Use the installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
```

### Windows

Use the PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/ArchAstro/archagents/main/install.ps1 | iex
```

## Claude Code Plugin

Add the marketplace and install the `archagents` plugin:

```text
/plugin marketplace add archastro/archagents
/plugin install archagents@archagents
```

The `archagents` plugin bundles everything: CLI install/auth commands, agent authoring, script and workflow builders, deployment, chat, config management, and impersonation. The `helper` plugin remains in `ArchAstro/claude-plugins`.

## Codex Plugin

To install the Codex plugin:

```text
git clone https://github.com/ArchAstro/archagents.git
cd /path/to/archagents
codex
/plugins
```

Then open the `ArchAstro` marketplace and install `archagents`. If the marketplace does not appear, restart Codex from the repository root and open `/plugins` again.

The marketplace definition lives in [`.agents/plugins/marketplace.json`](./.agents/plugins/marketplace.json), and the plugin manifests live under [`plugins/`](./plugins). For repo-local discovery, the marketplace must point at plugin directories using repo-root-relative `./plugins/...` paths.

Claude Code and Codex each load their own plugin tree (`.claude-plugins/archagents/` and `plugins/archagents/` respectively). Skill and command content is inlined into each tree — there is no shared source directory. When updating skill or command content, edit both copies.
