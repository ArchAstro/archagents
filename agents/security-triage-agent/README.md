# Security Triage Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Security Triage Agent from this repo.

1) Read agents/security-triage-agent/agent.yaml and agents/security-triage-agent/env.example
2) Ask me for: GITHUB_TOKEN (a PAT with repo scope), DEFAULT_REPO_OWNER, DEFAULT_REPO_NAME
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key GITHUB_TOKEN --value <token>
6) Deploy: cd agents/security-triage-agent && ./deploy.sh
7) Test it: create an agent session and ask it to scan a small repo for vulnerabilities
8) Show me the result
```

> 🛡️ **A senior security engineer that triages vulnerabilities, fixes what it can, and escalates the rest.**

Runs daily dependency scans, classifies findings into three explicit
outcomes (mitigated, auto-fixable, needs human attention), opens fix
PRs for the easy ones, and files GitHub issues for everything else
with full triage reasoning.

## What it does

### 1. Daily dependency scan (cron: 08:00 UTC)
- Reads your `mix.lock`, `package-lock.json`, etc. via the GitHub API
- Queries OSV.dev and the GitHub Advisory Database for known vulns
- Cross-references findings against your internal security policies (knowledge base)
- Triages each finding into one of three outcomes:
  - **A. Already mitigated / noise** → store decision in long-term memory, move on
  - **B. Small targeted fix** → create branch, commit fix, open PR
  - **C. Needs human attention** → file a GitHub issue with full reasoning

### 2. PR security review
- Polls open PRs every 15 minutes for security-relevant changes
- Reads the diff and flags concerns inline

### 3. Hourly log analysis
- Queries your logging service for auth anomalies, suspicious access,
  permission escalations
- Alerts via Slack on real signals (filters out routine noise)

## What makes the triage different

**The three explicit outcomes force a decision.** No "I'll come back to it later"
in long-term memory where humans can't see it. Every finding ends up in
exactly one place a human can actually look:
- A merged PR (auto-fix worked)
- An open GitHub issue (human attention needed)
- Long-term memory with a clear "noise" decision (won't be re-litigated next scan)

**Knowledge base grounding.** The agent loads your internal security
policies (patch management standard, InfoSec policy, etc.) as knowledge
sources. When triaging, it cites the relevant policy for severity
classification and remediation timelines instead of guessing.

**Dedup against past decisions.** Before triaging, it `memory_recall`s
past decisions on the same package and existing GitHub issues for the
same CVE — so it doesn't re-file the same finding every day.

## Setup

```bash
cp env.example .env
# Edit .env with your values
./deploy.sh
```

Then upload your security policy documents (see "Knowledge base setup" below).

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope. PRs and issues post as this account. |
| `DEFAULT_REPO_OWNER` | GitHub org for default scanning |
| `DEFAULT_REPO_NAME` | Default repo to scan |
| `DEFAULT_ECOSYSTEM` | `hex` for Elixir, `npm` for Node, `pip` for Python, etc. |
| `MONITORED_REPOS` | Comma-separated `owner/repo` list to scan |
| `SECURITY_TEAM_EMAIL` | Where to email scan summaries |

Optional:

| Variable | What it is |
|---|---|
| `GCLOUD_PROJECT_ID` | GCP project for log analysis |
| `GCLOUD_SA_KEY` | Service account JSON for read-only log access |

## Knowledge base setup

After deploying, upload your security policies. The agent's
`knowledge_search` will index them and reference them during triage.

```bash
./scripts/upload-policies.sh /path/to/your/policies/*.pdf
```

Recommended policies to upload:
- Patch Management Standard (severity → remediation timeline)
- InfoSec Policy
- Endpoint Security Standard
- Data Classification Standard
- Acceptable Use Policy
- Incident Response Plan

## Triage outcomes — examples

### Outcome A: Already mitigated
> CVE-2025-XXXXX in `axios@0.27.2` — vulnerable function is `formToJSON`
> which we don't use. We only call `axios.get` and `axios.post`. No exposure.
> Decision: noise. Stored in memory. Will not re-flag on future scans.

### Outcome B: Auto-fixed
> CVE-2025-YYYYY in `lodash@4.17.20` — prototype pollution in `_.set`.
> We use `_.set` in 3 places, all with literal keys. Per our patch
> management standard (high severity → 7 day SLA), this needs to be fixed.
> Created branch `security/fix-CVE-2025-YYYYY`, committed bump to `4.17.21`.
> PR #1234 opened.

### Outcome C: Filed as issue
> CVE-2025-ZZZZZ in `next@13.5.0` — server actions auth bypass. The fix
> requires upgrading to `15.x`, which is a major version bump that
> touches our middleware setup. Per patch management standard (critical →
> 48 hour SLA), this needs immediate attention but can't be auto-fixed.
> Filed issue #5678 with full triage and recommended upgrade path.

## Customization

### Different ecosystems
The shipped agent has scan logic for `hex`, `npm`, and `pip`. Add a new
ecosystem by extending `scripts/scan_dependencies.aascript` with the
matching lockfile parser.

### Different escalation channel
By default, escalations go to GitHub issues. To use Linear or Jira
instead, replace `create_github_issue` with `create_linear_issue` or
`create_jira_issue` (you'd write these as new scripts using their REST APIs).

### Different model
Triage benefits from strong reasoning. Recommended: Claude Sonnet or
Opus. Cheaper models will produce more false positives.

## What this demonstrates

- **Cron-driven routines** — daily scan, hourly logs, 15-min PR poll
- **Knowledge sources** — internal policies as searchable context
- **Long-term memory** — past triage decisions persist across scans
- **Custom scripts** — wraps OSV, GitHub Advisories, GCP Logging APIs
- **GitHub App integration** — read code, create branches, open PRs, file issues
- **Slack integration** — log anomaly alerts
- **Multi-routine agent** — one agent, three different schedules

## Files

```
security-triage-agent/
├── README.md
├── agent.yaml                   # AgentTemplate config
├── env.example
├── deploy.sh
├── scripts/
│   ├── query_osv.aascript
│   ├── query_github_advisories.aascript
│   ├── scan_dependencies.aascript
│   ├── get_repo_file.aascript
│   ├── create_branch.aascript
│   ├── commit_file.aascript
│   ├── create_pull_request.aascript
│   ├── create_github_issue.aascript
│   ├── query_gcloud_logs.aascript
│   └── upload-policies.sh
├── skills/
│   └── security-triage/SKILL.md
└── examples/
    ├── sample-triage-noise.md
    ├── sample-triage-autofix.md
    └── sample-triage-escalation.md
```
