# Example: FDE runs a first engagement

Transcript of the FDE agent walking a new customer from "we want to
ship an agent" to a live, deployed agent in a single thread session.

---

> **Dev**: We want to build an agent that reviews our PRs. How do we
> start?

> **FDE**: Quick discovery — five questions:
> 1. Which repo(s) should it review?
> 2. What kind of feedback do you want it to leave — bugs, style,
>    architecture, all of the above?
> 3. Should it approve, request changes, or only comment?
> 4. What should it *never* flag?
> 5. How will you know it's working?
>
> Answer those and I'll draft an `agent.yaml` inline.

---

> **Dev**: One repo — `acme/api`. We want bug feedback only, no
> style. Comments only, no approvals. Never flag formatting or
> missing tests. Working = no reverts caused by issues we would have
> caught.

> **FDE**: Got it. Mapping to integration pattern 1 — GitHub PR webhook
> routine + inline comments.
>
> Here's the skeleton:
>
> ```yaml
> kind: AgentTemplate
> agent_key: acme-api-reviewer
> name: Acme API Reviewer
> identity: |
>   You review PRs on acme/api. You flag bugs only — never style,
>   never missing tests, never formatting. Comments only, never
>   approve. Your working definition of "a real bug": a change
>   that would cause a revert in production.
>   ...
> tools:
>   - kind: builtin
>     builtin_tool_key: skills
>     status: active
>   - kind: custom
>     name: get_pr_files
>     handler_type: script
>     config_ref: acme-get-pr-files
>     ...
> routines:
>   - name: review-prs
>     handler_type: preset
>     preset_name: do_task
>     event_type: webhook.github_app.pull_request
>     event_config:
>       webhook.github_app.pull_request:
>         filters: {}
>     status: active
> installations:
>   - kind: integration/github
>     config: {}
>   - kind: memory/long-term
>     config: {}
> ```
>
> Before we build the scripts for the custom tools, install the
> ArchAstro GitHub App on `acme/api`. Done? I'll generate the
> `.aascript` files next.

---

> **Dev**: Installed. What now?

> **FDE**: Loading `archagent-build-script`. I'll scaffold `scripts/get-pr-files.aascript`,
> `scripts/list-pr-reviews.aascript`, and `scripts/create-pr-review.aascript`.
> Want me to drop them here for review, or write them straight into your
> `configs/` directory?

---

> **Dev**: Write them in.

> **FDE**: Initializing `configs/` first — loading `archagent-manage-configs`.
> Running:
>
> ```
> archagent init --enable-configs
> ```
>
> Then writing scripts and AgentTemplate. I'll validate each with
> `archagent validate config -k Script -f ...` before we deploy.
>
> …validated. Deploying:
>
> ```
> archagent deploy configs
> archagent deploy agent agent.yaml
> ```
>
> The agent is live as `acme-api-reviewer`. Next PR on acme/api will
> trigger it.
>
> Storing engagement memory under `fde_engagements` / `acme` so next
> session I pick up without re-asking. Handoff doc in 30 seconds — 5
> sections (what it does, what it won't do, how to update, how to
> debug, who to call).

---

The session continues with the handoff doc. Next time the dev opens a
thread, the FDE reloads the memory and resumes in context.
