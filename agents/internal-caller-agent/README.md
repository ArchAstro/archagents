# Internal Caller Agent

## Deploy with your coding agent

Paste this into Claude Code, Codex, or any AI coding assistant:

```
Deploy the Internal Caller Agent from this repo.

1) Read agents/internal-caller-agent/agent.yaml and agents/internal-caller-agent/env.example
2) Install the ArchAgents CLI if missing: brew install ArchAstro/tools/archagent
3) Run: archagent auth login <my-email> && archagent init
4) Deploy: archagent install agentsample internal-caller-agent
5) Create a demo bearer token: TOKEN="$(openssl rand -hex 32)"
6) Set it on the deployed agent: archagent create agentenvvar --agent <agent-id> --key AGENT_BEARER_TOKEN --value "$TOKEN"
7) Test it: create an agent session and ask it to call get_auth_status
8) Confirm the response says authenticated=true, status=200, token_was_echoed=true, and token_matched_secret=true
```

> Demonstrates outbound API authentication with an agent-scoped bearer token.

This sample is intentionally small: one agent, one script-backed custom
tool, and one agent environment variable. The tool calls
`https://httpbin.org/bearer` with:

```bash
curl -sS "https://httpbin.org/bearer" \
  -H "Authorization: Bearer $AGENT_BEARER_TOKEN"
```

The token is stored as an agent-scoped secret, so it is available to this
agent's server-side scripts without exposing it in the agent template or
tool arguments.

## What it does

When asked to check auth, the agent calls `get_auth_status`. The script:

1. Reads `env.AGENT_BEARER_TOKEN`
2. Sends it as a bearer token in the `Authorization` header
3. Reads httpbin's response
4. Returns a safe summary:
   - `authenticated`
   - HTTP `status`
   - `token_was_echoed`
   - `token_matched_secret`

It does not return the full bearer token.

## Setup

Deploy the sample:

```bash
archagent install agentsample internal-caller-agent
```

Then create the agent-scoped secret. Use the deployed agent ID printed by
the install command:

```bash
TOKEN="$(openssl rand -hex 32)"

archagent create agentenvvar \
  --agent <agent-id> \
  --key AGENT_BEARER_TOKEN \
  --value "$TOKEN" \
  --description "Demo bearer token for authenticated outbound request sample"
```

## Test it

Create a short session:

```bash
archagent create agentsession \
  --agent <agent-id> \
  --instructions "Call get_auth_status once and report the result." \
  --wait
```

Expected result:

```text
authenticated: true
status: 200
token_was_echoed: true
token_matched_secret: true
```

## Why agent-scoped secrets

Use agent-scoped environment variables when a credential belongs to one
agent's job. Compared with org-scoped variables, this keeps the blast
radius smaller: another agent in the same org cannot read this token just
because it can run scripts.

For shared credentials, use an org-scoped env var instead and reference it
from multiple agents.

## What this demonstrates

- Script-backed custom tools
- Agent-scoped environment variables
- Bearer-token `Authorization` headers
- Server-side HTTP calls from an agent tool
- Avoiding secrets in tool inputs, templates, and chat transcripts

## Files

```text
internal-caller-agent/
|-- README.md
|-- agent.yaml
|-- env.example
|-- sample.yaml
`-- scripts/
    `-- get-auth-status.aascript
```
