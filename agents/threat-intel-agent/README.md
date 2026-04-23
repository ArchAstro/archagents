# Threat Intelligence Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Threat Intelligence Agent from this repo.

1) Read agents/threat-intel-agent/agent.yaml and agents/threat-intel-agent/env.example
2) Ask me for: GITHUB_TOKEN (a PAT with repo scope), MONITORED_REPOS (comma-separated owner/repo list), BRIEF_REPO (where to file the daily brief)
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key GITHUB_TOKEN --value <token>
6) Deploy: archagent install agentsample threat-intel-agent
7) Test it: create an agent session and ask it to generate today's threat brief
8) Show me the result
```

> 📰 **Your daily security analyst.** Reads HN, GitHub Advisories, and the major CVE feeds every morning. Tells you only what matters to YOUR stack.

A focused agent that runs once a day and produces a curated threat
intelligence brief. No noise, no daily 50-CVE dumps — just the things
that affect packages you actually use, with concrete recommendations.

## What it does

Every morning at 07:00 UTC:

1. **Scans Hacker News** for security stories from the last 24 hours
   (filtered by points so you only see what's actually trending)
2. **Scans GitHub Security Advisories** for high/critical CVEs in your
   ecosystems
3. **Cross-references against your codebase** — does this package
   exist in your `mix.exs` / `package.json` / `requirements.txt`?
4. **Recalls past briefs** to identify recurring patterns
   ("third LLM proxy CVE this month")
5. **Files exposure issues** as GitHub issues with `severity:*` labels
6. **Posts the daily brief** as a GitHub issue with `[security, threat-brief]`
   labels
7. **Sends a scannable Slack summary** to your security channel

## Why this exists

Most teams learn about security incidents the wrong way:
- Twitter / HN, hours or days after the fact
- An overnight Slack thread that nobody reads
- A dashboard that nobody opens
- A 200-CVE daily report that everyone ignores

The Threat Intel Agent solves this by being **selective and contextual**:

- **Selective** — uses HN points + GitHub severity to filter signal from noise
- **Contextual** — reads YOUR lockfiles to determine if you're actually exposed
- **Persistent** — past decisions live in long-term memory, so day 30 says
  "this is the 4th SSRF in the LLM proxy ecosystem this quarter"
- **Actionable** — every direct exposure becomes a GitHub issue with recommendations

## Setup

```bash
# 1. Set each required env var on your ArchAstro org. The agent's
#    scripts read these at runtime — env.example lists what's needed.
for var in $(grep -oE '^[A-Z_]+' env.example); do
  read -rsp "$var: " value; echo
  archagent create orgenvvar --key "$var" --value "$value"
done

# 2. Deploy
archagent install agentsample threat-intel-agent
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope. Issues will post as this account. |
| `MONITORED_REPOS` | Comma-separated `owner/repo` list to check for exposure |
| `STACK_DESCRIPTION` | One-line description of your stack (e.g. `"Elixir/Phoenix backend, Next.js frontend, GCP infra, Stripe billing"`). Helps the agent decide what's relevant. |
| `BRIEF_REPO` | Where to file the daily brief issue (e.g. `your-org/your-repo`) |
| `SLACK_CHANNEL` | Slack channel to post the summary (e.g. `#security`) |

## Sample output

The daily brief, filed as a GitHub issue:

```markdown
# threat-brief: 2026-04-08 — 12 stories scanned, 1 direct exposure, 3 watch items

## 🔴 Top story
CVE-2026-25639 — DoS in axios <1.13.5 via __proto__ key in mergeConfig.
Reachable via any code path that passes user-controlled JSON to axios config.

## ⚠️ Direct exposures
- **axios 1.13.4** in `services/backend/package.json` → CVE-2026-25639
  - Severity: HIGH (per patch management standard, fix within 7 days)
  - Recommendation: bump to 1.13.5
  - Filed: #1234

## 👀 Watch list
- LLM proxy supply chain — third incident this month
- Next.js 15 server actions — public discussion of auth bypass surface
- GitHub Actions third-party action audit gaining traction

## ✅ No action needed
- Log4Shell variant in obscure JVM lib (we don't run JVM)
- WordPress plugin RCE (we don't use WordPress)
- Cisco firmware (no exposure)
```

The Slack summary (15 lines max, links to the GitHub issue):

```
🛡️ Security Threat Brief — Apr 8

🔴 Top: axios <1.13.5 DoS (CVE-2026-25639)

🚨 1 exposure:
• axios 1.13.4 in services/backend → fix to 1.13.5 (#1234)

👀 Watching: LLM proxy supply chain (3rd this month)

Full brief: https://github.com/your-org/your-repo/issues/3606
```

## Customization

### Different ecosystems
The shipped agent watches `hex` and `npm`. To add more, edit the
`daily-threat-brief` routine instructions to call `list_recent_advisories`
with your ecosystem (`pip`, `RubyGems`, `Maven`, etc.).

### Different time
Change the cron schedule in `agent.yaml`. Default is `0 7 * * *` (07:00 UTC).

### Different delivery
Currently posts to GitHub issues + Slack. To add email, append a
`send_email` step to the routine instructions and use the `email`
namespace in scripts.

## What this demonstrates

- **Cron-driven routines** that orchestrate multiple data sources
- **Selective web querying** via lightweight scripts (HN Algolia, GitHub Advisories)
  instead of broad web scraping
- **Long-term memory** for cross-day pattern recognition
- **GitHub issue + Slack delivery** in a single routine
- **Stack-aware filtering** — the agent knows YOUR dependencies and only
  flags what's actually relevant

## Files

```
threat-intel-agent/
├── README.md
├── agent.yaml
├── env.example
├── scripts/
│   ├── search_hn_security.aascript    # HN Algolia API
│   ├── list_recent_advisories.aascript # GitHub Advisories filtered by date
│   ├── get_repo_file.aascript         # read mix.exs / package.json
│   └── create_github_issue.aascript   # file the brief and exposures
└── examples/
    └── sample-brief.md
```
