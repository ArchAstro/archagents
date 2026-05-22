# Compliance Reviewer Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Compliance Reviewer Agent from this repo.

1) Read agents/compliance-reviewer/agent.yaml — the `setup_requirements:` block lists everything you'll need.
2) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
3) Run: archagent auth login <my-email> && archagent init
4) Deploy: archagent install agentsample compliance-reviewer
5) Open the agent in the developer portal. Its "Finish setup" panel lists every required env var, install, and verifier.
6) Walk me through each action: ask for the values it needs, install integrations on prompt, and confirm each verifier turns green.
7) Test it: create an agent session and ask it to review a PR for compliance.
8) Show me the result.
```

> **Reviews every PR against your compliance rules.** SOC2, GDPR,
> HIPAA, internal data handling policies — define the rules once,
> the agent enforces them on every change.

A specialized PR reviewer that doesn't review code quality (the
Code Review Agent does that). It reviews **compliance**: does this
PR introduce something that would violate SOC2 access controls?
Does it log PII without redaction? Does it write to a database
without an audit trail?

## What it does

When a PR opens:

1. **Reads the diff** via the GitHub API
2. **Loads the compliance rules** from the knowledge base
3. **Categorizes changes** that touch compliance-relevant code:
   - Auth / authorization
   - PII handling (logging, storage, transmission)
   - Audit logging
   - Data retention
   - Encryption (in transit / at rest)
   - Access control changes
4. **Posts inline comments** for any rule violations, citing the
   specific compliance standard
5. **Stays silent** if the PR doesn't touch compliance-relevant code

## Why this is separate from the Code Review Agent

- **Different rules** — compliance has objective "yes/no" criteria
  that don't need engineering judgment
- **Different cadence** — compliance issues are usually rarer than
  code quality issues, so the noise floor matters more
- **Different audience** — compliance findings often need to go to
  a security/compliance officer, not just the PR author
- **Different model** — strict rule-following benefits from a
  smaller, faster model than open-ended code review

Deploy both on the same repo. The Code Review Agent reviews code
quality; the Compliance Reviewer checks the rules.

## Setup

```bash
archagent install agentsample compliance-reviewer
```

After install, open the agent in the developer portal. The "Finish
setup" panel — populated from `setup_requirements:` in `agent.yaml` —
drives the rest:

- **Env vars** are stored per-agent (`scope: agent_env_var`), so the
  installer always has write access without needing org admin rights.
- **Integration installs** (the GitHub App) link out to the install
  URL — install it on every repo whose PRs you want compliance-reviewed.
- **Custom verifiers** (e.g. confirming `GITHUB_TOKEN` is valid) re-run
  on a daily sweep, so a deleted secret or revoked install transitions
  back to `:degraded` until you fix it.

The sample ships with a seed set of rules under `rules/*.md` that are
uploaded to the agent's knowledge base automatically as part of the
install. To add your own rules later, use the generic knowledge flow:

```bash
# Find the installation the seed rules live on
INSTALLATION=$(archagent list agentinstallations --agent compliance-reviewer -o json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d['data'] if i['kind']=='archastro/files']" | head -1)

# For each rule file:
FILE_ID=$(archagent create files \
  --data "$(base64 < /path/to/your/rule.md)" \
  --filename rule.md --content-type text/markdown \
  | grep -oE 'fil_[A-Za-z0-9]+' | head -1)
archagent create agentinstallationsources \
  --installation "$INSTALLATION" \
  --type file/document \
  --payload "{\"file_id\": \"$FILE_ID\"}"
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | GitHub token used by the sample's custom scripts. Inline comments post as this account. Prefer a fine-grained PAT with Contents: read, Pull requests: read/write, and Metadata: read. A classic `repo` token also works but is broader. |
| `BOT_LOGIN` | The PAT account's GitHub username (for dedup) |

## Compliance rules format

The agent reads compliance rules from its knowledge base. Format
each rule as a markdown file with this structure:

```markdown
# RULE-001: PII must not be logged

## Standard
SOC2 CC6.7, GDPR Article 32

## Applies to
Any code that calls a logger (Logger.info, Logger.debug, console.log,
log.info, etc.)

## Detection
- Search for log statements that interpolate variables matching
  PII patterns: email, phone, ssn, dob, full_name, address
- Flag if any of these variables are passed without `redact()` wrapper

## Severity
HIGH

## Suggested fix
Wrap PII fields with the `redact/1` helper:
`Logger.info("user signed in", user_id: redact(user.email))`

## Exception
If the PR is in a test file, this rule does not apply.
```

The agent indexes these as knowledge sources and looks them up when
reviewing a PR.

## Sample interactions

### Violation found
> **Compliance Reviewer (inline comment on `your-app/routes/users.py:45`):**
>
> 🚨 **RULE-001 violation: PII in logs** (SOC2 CC6.7, GDPR Article 32)
>
> This `logger.info` call interpolates `user.email` directly, which
> exposes PII in logs.
>
> **Fix:** wrap with the `redact()` helper:
> `logger.info("user signed in", extra={"user_id": redact(user.email)})`

### No violations found
The agent posts nothing. Silence = compliance.

## Customization

### Different compliance frameworks
Upload your own rule files. The shipped agent has zero hardcoded
rules — everything comes from the knowledge base. Use it for SOC2,
HIPAA, PCI DSS, GDPR, internal policies, or any combination.

### Different severity bar
Edit the agent identity to change which severities get inline
comments vs. silently logged. Default: HIGH and CRITICAL get
inline comments, MEDIUM gets a single summary comment, LOW is silent.

### Different report destination
By default, the agent posts inline comments. To also notify a
compliance officer via email, add `email/send` to the routine.

## What this demonstrates

- **Webhook routine** triggered by `webhook.github_app.pull_request`
- **Knowledge base as policy source** — rules are config, not code
- **Reused custom scripts** from the code-review-agent (get_pr_files, get_repo_file, create_pr_review)
- **Single-purpose agent** — does ONE thing well

## Files

```
compliance-reviewer/
├── README.md
├── agent.yaml
├── env.example
├── scripts/
│   ├── get_pr_files.aascript
│   ├── get_repo_file.aascript
│   ├── list_pr_reviews.aascript
│   └── create_pr_review.aascript
├── rules/                           # Sample compliance rules
│   ├── pii-not-logged.md
│   ├── audit-trail-required.md
│   └── encryption-at-rest.md
└── examples/
    └── sample-violation.md
```
