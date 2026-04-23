# Release Notes Bot

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Release Notes Bot from this repo.

1) Read agents/release-notes-bot/agent.yaml and agents/release-notes-bot/env.example
2) Ask me for: GITHUB_TOKEN (a PAT with repo scope), REPO_OWNER, REPO_NAME
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Set org env vars: archagent create orgenvvar --key GITHUB_TOKEN --value <token>
6) Deploy: archagent install agentsample release-notes-bot
7) Test it: create an agent session and ask it to draft release notes for the last week
8) Show me the result
```

> 📝 **Drafts your weekly changelog from the merged PRs.**

A scheduled agent that watches your merged PRs and writes a clean,
human-readable changelog entry every week. Groups changes by type
(features, fixes, breaking), highlights anything that needs special
attention (migrations, deprecations), and files the draft as a
GitHub issue you can review and copy into `CHANGELOG.md`.

## What it does

Every Monday at 10:00 UTC:

1. **Lists merged PRs** from the last 7 days via the GitHub API
2. **Reads each PR's title, body, and labels** (no need to dig into the diff)
3. **Categorizes** by conventional commit prefix (`feat:`, `fix:`, `docs:`, `chore:`, etc.) or by labels
4. **Drafts a changelog entry** with sections:
   - Highlights (1-3 most user-visible changes)
   - Features
   - Fixes
   - Breaking changes
   - Internal/maintenance
5. **Files the draft as a GitHub issue** with `[release-notes, draft]` labels
6. **Stores the date range in memory** so the next run picks up where this one left off

## Why this beats `git log`

`git log` gives you commit messages. The Release Notes Bot gives you
**a publication-ready changelog** that:
- Groups by user-facing impact, not chronological order
- Filters out internal noise (chores, version bumps, dependency updates)
- Highlights breaking changes and migrations explicitly
- Reads PR bodies for context, not just titles
- Cross-references issue links so users can dig in

## Setup

```bash
cp env.example .env
# Edit .env with your values
archagent install agentsample release-notes-bot
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope |
| `REPO_OWNER` | GitHub org |
| `REPO_NAME` | Repo to watch |
| `RELEASE_BRANCH` | Branch to track (usually `main`) |

## Sample output

The bot files something like this as a GitHub issue:

```markdown
# Release Notes Draft — Week of 2026-04-08

## ✨ Highlights
- Code Review Bot now reviews PRs as the GitHub App identity (#101)
- Security Agent escalates findings as GitHub issues with severity labels (#102)
- Threat Intel Agent: daily security brief delivered to #security (#103)

## Features
- feat(collaboration-network): collaboration section on network detail page (#104)
- feat(collaboration-network): activity feed firehose + scoped tabs (#105)
- feat: Code Review Bot can resolve own review threads (#106)

## Fixes
- fix(routines): update routine_run_id on session reuse (#107)
- fix: log analyzer only alerts on real auth failures (#108)

## Breaking changes
None this week.

## Internal
- chore: bump dependencies
- docs: update README

---
*Generated from 23 merged PRs between 2026-04-01 and 2026-04-08.
Review and copy to CHANGELOG.md, or close this issue if no release this week.*
```

## Customization

### Different cadence
Edit the cron in `agent.yaml`. Default is `0 10 * * 1` (10:00 UTC Mondays).

### Different categorization
Edit the agent identity prompt to change how PRs are grouped. The
shipped logic uses conventional commit prefixes. You could group
by area (`(auth)`, `(billing)`) instead.

### Auto-commit to CHANGELOG.md
By default the bot files a draft issue. To auto-commit instead:
- Add `commit_file` to the agent's tools
- Update the routine instructions to commit to `CHANGELOG.md` on a
  branch and open a PR

## What this demonstrates

- **Cron routines** with scheduled work
- **GitHub API list operations** with date filters
- **Long-term memory** for "last run" tracking
- **Structured output** (the bot writes markdown, not freeform prose)

## Files

```
release-notes-bot/
├── README.md
├── agent.yaml
├── env.example
├── scripts/
│   ├── list_merged_prs.aascript     # GET /repos/{o}/{r}/pulls?state=closed&base=main
│   └── create_github_issue.aascript # file the draft
└── examples/
    └── sample-changelog.md
```
