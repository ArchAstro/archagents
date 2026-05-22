# Cross-Org Collaboration Agent Sample

An engineering agent that participates directly in cross-organization
threads without leaking source code, secrets, internal paths, or
schemas. Every outgoing message passes through a six-step pipeline —
a structured-output schema plus five field guards (regex, substring,
two cross-vendor LLM judges, and a self-attestation verifier) —
before it can post.

## Architecture

![Architecture overview](diagrams/architecture.svg)

Triggered by direct messages in a cross-org thread. The agent reads
your private repo via the GitHub App, drafts a structured response
(`summary`, `interface_shape`, `proposed_approach`,
`questions_for_partner`, `next_steps`, `safety_self_check`), and
runs it through five field guards defined in
`schemas/cross-org-hardened.yaml`. Only messages that pass every
layer post to the shared thread; rejections feed back to the agent
for a rewrite.

## Install

```sh
archagent install agentsample cross-org-collab-agent-sample
```

## Required env vars

| Variable | Required | What it is |
|---|---|---|
| `GITHUB_TOKEN` | Required | Fine-grained PAT (or classic `repo` token) the agent uses to read your private repo, create branches, commit files, and open PRs. Recommended scopes: Contents: read/write, Pull requests: read/write, Metadata: read. |
| `REPO_OWNER` | Required | GitHub org owning the repo the agent reads from. |
| `REPO_NAME` | Required | Repo name. |
| `STACK_DESCRIPTION` | Required | One-line architecture description woven into the agent's identity prompt (e.g. `"Python/Django backend, React frontend, AWS infra"`). |

## Bundle layout

- `agents/cross-org-collab-agent-sample.yaml` — the agent config
- `solution.yaml` — catalog metadata
- `tools/` — five tool definitions: `get_repo_file`, `create_branch`, `commit_file`, `create_pull_request`, `create_github_issue`
- `schemas/` — `cross-org-hardened.yaml` defining the structured output schema and the five field guards
- `scripts/` — implementations of the GitHub tools
- `examples/` — `allowed-message.md` (passes all guards) and `blocked-message.md` (code-leak attempt, rejected)
- `env.example` — required env vars (see above)

## Local validation

```sh
uv run scripts/sample_tool.py generate --check
uv run scripts/sample_tool.py pack solutions/cross-org-collab-agent-sample
```
