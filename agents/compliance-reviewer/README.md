# Compliance Reviewer Agent

> ⚖️ **Reviews every PR against your compliance rules.** SOC2, GDPR,
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

You run BOTH on the same PRs. your code-review bot reviews the code, the Compliance
Reviewer reviews the rules.

## Setup

```bash
cp env.example .env
./deploy.sh
./upload-rules.sh /path/to/your/compliance/rules/*.md
```

## Required env vars

| Variable | What it is |
|---|---|
| `GITHUB_TOKEN` | PAT with `repo` scope |
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
├── deploy.sh
├── upload-rules.sh
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
