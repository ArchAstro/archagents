# Sample Solutions

Catalog-ready Solution bundles for ArchAgents. Each sample imports one
deployable AgentTemplate and, where applicable, standalone
AgentToolTemplate and AgentRoutineTemplate rows.

| Solution | What it ships |
|---|---|
| [archastro-sample](archastro-sample) | Default ArchAstro project concierge |
| [archastro-onboarding-sample](archastro-onboarding-sample) | Guided first-agent onboarding |
| [code-review-agent-sample](code-review-agent-sample) | PR review AgentTemplate plus custom GitHub review tools |
| [compliance-reviewer-sample](compliance-reviewer-sample) | Compliance PR review AgentTemplate plus review tools |
| [cross-org-collab-agent-sample](cross-org-collab-agent-sample) | Cross-org collaboration AgentTemplate and GitHub edit tools |
| [fde-agent-sample](fde-agent-sample) | Forward Deployed Engineer AgentTemplate |
| [onboarding-qa-sample](onboarding-qa-sample) | New-hire Q&A AgentTemplate |
| [platform-health-agent-sample](platform-health-agent-sample) | Platform health AgentTemplate plus scheduled/webhook routines |
| [release-notes-bot-sample](release-notes-bot-sample) | Weekly release notes AgentTemplate plus GitHub tools |
| [security-triage-agent-sample](security-triage-agent-sample) | Security triage AgentTemplate plus custom tools and routines |
| [threat-intel-agent-sample](threat-intel-agent-sample) | Threat intelligence AgentTemplate plus GitHub and feed tools |

Validate after edits:

```bash
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py lint --strict
```
