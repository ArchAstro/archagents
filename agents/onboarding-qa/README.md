# Onboarding Q&A Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Onboarding Q&A Agent from this repo.

1) Read agents/onboarding-qa/agent.yaml and agents/onboarding-qa/env.example
2) No env vars required — this agent works out of the box
3) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
4) Run: archagent auth login <my-email> && archagent init
5) Deploy: archagent install agentsample onboarding-qa
6) Test it: upload the bundled sample FAQ, create an agent session, and ask "What's the PTO policy?"
7) Show me the result
```

> 🎓 **The new-hire question answerer that doesn't get tired.**

Drops your company's docs, runbooks, and policies into a knowledge
base and answers new employees' questions about how things work.
Searches semantically, cites sources, and admits when it doesn't know.

## What it does

- Sits in a thread (or Slack channel) where new hires ask questions
- Searches your uploaded knowledge base via `knowledge_search`
- Answers in plain language, with **citations** to the source doc
- For things outside the knowledge base, suggests who to ask instead
  ("This is a billing question — try @finance")
- Tracks recurring questions in long-term memory so you can spot
  documentation gaps

## Why this exists

New hires ask the same questions over and over. Veterans get tired
of answering them. Slack threads get lost. Wikis go stale. The
Onboarding Q&A Agent solves this by being:

- **Always available** — no waiting for someone to wake up
- **Source-grounded** — every answer cites the actual doc
- **Honest about limits** — won't invent answers it doesn't have
- **A documentation gap detector** — its memory shows you which
  questions get asked repeatedly so you can update the docs

## Setup

```bash
# 1. Set each required env var on your ArchAstro org. The agent's
#    scripts read these at runtime — env.example lists what's needed.
for var in $(grep -oE '^[A-Z_]+' env.example); do
  read -rsp "$var: " value; echo
  archagent create orgenvvar --key "$var" --value "$value"
done

# 2. Deploy
archagent install agentsample onboarding-qa
```

The sample ships with a short seed FAQ (`knowledge/sample-faq.md`) that
gets uploaded automatically as part of the install so the agent has
something to answer from on day one. Real rollouts replace that seed
with your own onboarding docs — see "Knowledge upload" below.

## Required env vars

| Variable | What it is |
|---|---|
| `COMPANY_NAME` | Used in the agent's voice |

That's it. No GitHub token, no Slack token (unless you want Slack delivery).

## Knowledge upload

After deploying, upload your onboarding docs via the platform's
standard knowledge-ingestion flow:

```bash
# Find the agent's archastro/files installation (created at deploy time)
INSTALLATION=$(archagent list agentinstallations --agent onboarding-qa -o json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d['data'] if i['kind']=='archastro/files']" | head -1)

# For each doc, base64-encode and attach as a source:
for doc in /path/to/onboarding/*.pdf /path/to/onboarding/*.md; do
  filename=$(basename "$doc")
  content_type=$(case "$filename" in
    *.pdf) echo "application/pdf" ;;
    *.md)  echo "text/markdown" ;;
    *)     echo "application/octet-stream" ;;
  esac)
  FILE_ID=$(archagent create files \
    --data "$(base64 < "$doc")" \
    --filename "$filename" --content-type "$content_type" \
    | grep -oE 'fil_[A-Za-z0-9]+' | head -1)
  archagent create agentinstallationsources \
    --installation "$INSTALLATION" \
    --type file/document \
    --payload "{\"file_id\": \"$FILE_ID\"}"
done
```

The agent indexes the uploaded files automatically and they become
searchable.

Recommended docs to upload:
- Employee handbook
- Dev environment setup guide
- Team / org chart
- Codebase architecture overview
- Deployment / release process
- Incident response playbook
- Glossary of internal acronyms
- Common workflows (PR, code review, deploy, etc.)
- Company values / decision-making process

## Sample interaction

> **New hire:** How do I get production database access?
>
> **Onboarding Q&A:** Production database access is granted via the
> `prod-db-access` Linear request. You'll need:
> 1. Manager approval (your manager creates the Linear ticket)
> 2. Completion of the data handling training (linked in the employee handbook §4.2)
> 3. SSH key registered with the bastion host (see [dev environment setup](#) §6)
>
> Source: *Employee Handbook §4.2 — Production Access Policy*
>
> If you have questions about the training or the bastion, ask in #devops.

## Customization

### Different voice
Edit the agent identity to match your company's tone — formal,
casual, jokes, etc.

### Slack delivery
To make this a Slack bot, install the `integration/slack_bot` and add
a routine that fires on `webhook.slack.app_mention`.

### Different knowledge sources
The shipped agent uses uploaded files. You can also add `web/site`
sources to ingest live docs (Confluence, Notion, GitHub wiki) when
the platform's web ingestion is more reliable.

## What this demonstrates

- **`knowledge_search` builtin** as the primary capability
- **File upload via `archastro/files` installation**
- **Long-term memory** for tracking recurring questions (gap detection)
- **A simple agent with zero custom scripts** — proof that not every
  agent needs to be complex

## Files

```
onboarding-qa/
├── README.md
├── agent.yaml             # All builtin tools, no custom scripts
├── env.example
├── knowledge/
│   └── sample-faq.md      # Seed FAQ uploaded automatically on install
└── examples/
    └── sample-conversation.md
```
