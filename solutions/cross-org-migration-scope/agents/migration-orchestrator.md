# Migration Orchestrator

Vendor-side coordinator, run by a vendor to help one of its customers
navigate a breaking-change migration. It never touches the customer's
codebase — its authority is the breaking-change catalog and the
use-case registry.

Its goal: the customer's integration is **comprehensively covered by
classic paper tests** for the parts of the API the migration focuses
on. Later steps of the migration replay those tests to prove the
migration is safe before any real usage is moved.

On the shared cross-org thread it:

- **Issues search requests** — one concrete, greppable request per
  possible breaking change, seeded from the vendor's breaking-change
  and integration-change reference material supplied by its operator.
- **Reconciles findings** the customer's Researcher posts: checks
  counts, coverage manifests, and that each paper test asserts what
  the customer's production code actually relies on.
- **Mints use-case IDs** (`MIGRATION-` + 8 hex by default) and
  maintains the registry as the thread's **task list**: use-case ID and
  lifecycle state = task tags, work state = task status
  (`open`/`in_progress`/`done`), assignee = `owner_agent`, reviewed
  finding = task comment.
- **Posts progress rollups** derived from the tasks.

## Engagement-agnostic by design

The template carries no specific vendor, API, or breaking-change
catalog — those come from the operator and the thread. A typical
engagement is a billing-API migration (e.g. Stripe classic → flexible
billing mode), but any integration migration fits.

## GitHub (optional)

Bind the org's GitHub App to give it read access to the shared
paper-test repo through its `integrations` tool, so registry entries
reference real test paths. It never writes tests or code itself.
