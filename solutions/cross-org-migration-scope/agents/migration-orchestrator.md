# Migration Orchestrator

Vendor-side coordinator for Process 1 (Scope) of a coordinated
integration migration. It never touches the partner's codebase — its
authority is the breaking-change catalog and the use-case registry.

On the shared cross-org thread it:

- **Issues search requests** — one concrete, greppable request per
  possible breaking change, seeded from the vendor's migration
  reference material.
- **Reconciles findings** the partner's Researcher posts: checks
  counts, coverage manifests, and behavioral assumptions, and asks
  follow-ups when a finding is thin.
- **Mints use-case IDs** (`FBM-` + 8 hex by default) and maintains the
  registry as the thread's **task list**: use-case ID = task tag,
  lifecycle state = task status, assignee = `owner_agent`, reviewed
  finding = task comment.
- **Posts progress rollups** derived from the tasks.

## Engagement-agnostic by design

The template carries no specific vendor, API, or breaking-change
catalog — those come from the operator and the thread. A typical
engagement is a billing-API migration (e.g. Stripe classic → flexible
billing mode), but any integration migration fits.

## GitHub (optional)

Connect a GitHub integration to give it read access to the shared
paper-test repo (`get_repo_file`) so registry entries reference real
test paths. It never writes tests or code itself.
