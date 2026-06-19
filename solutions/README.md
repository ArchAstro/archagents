# Sample Solutions

Catalog-ready agent bundles. Each one installs as a single Solution
and shows up in the catalog with its agent config, tools, and
routines ready to deploy.

| Solution | What it ships |
|---|---|
| [archastro-catalog-taxonomy](archastro-catalog-taxonomy) | Hidden config-only bundle of every SolutionCategory + SolutionTag the catalog ships |
| [archastro-sample](archastro-sample) | Default ArchAstro project concierge |
| [archastro-onboarding-sample](archastro-onboarding-sample) | Guided first-agent onboarding |
| [code-review-agent-sample](code-review-agent-sample) | PR review agent + custom GitHub review tools |
| [compliance-reviewer-sample](compliance-reviewer-sample) | Compliance PR review agent + review tools |
| [cross-org-collab-agent-sample](cross-org-collab-agent-sample) | Cross-org collaboration agent + GitHub edit tools |
| [fde-agent-sample](fde-agent-sample) | Forward Deployed Engineer agent |
| [onboarding-qa-sample](onboarding-qa-sample) | New-hire Q&A agent |
| [platform-health-agent-sample](platform-health-agent-sample) | Platform health agent + scheduled and webhook routines |
| [release-notes-bot-sample](release-notes-bot-sample) | Weekly release notes agent + GitHub tools |
| [security-triage-agent-sample](security-triage-agent-sample) | Security triage agent + custom tools and routines |
| [threat-intel-agent-sample](threat-intel-agent-sample) | Threat intelligence agent + GitHub and feed tools |

Validate after edits:

```bash
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py lint --strict
```
