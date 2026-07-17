# Shared Test Suite

Turn automated CI results into an internal shared test channel. This Solution
accepts signed `test_run` webhooks, posts a deterministic summary to one
team-owned thread per suite, and has a reporter agent generate a Markdown run
artifact.

```text
GitHub Actions → generic webhook → Test Ingest automation → tests:<suite_id>
                                      └→ Test Reporter agent → run artifact
```

## Included components

- `custom_objects/` — `TestSuite`, `Test`, `TestRun`, and `TestResult`
  schemas for structured suite/run history.
- `workflows/test-ingest-workflow.yaml` — mode resolution, internal thread
  routing, summary posting, and best-effort object writes.
- `automations/test-ingest.yaml` — trigger automation for
  `webhook.external.test_run`.
- `agents/shared-test-suite.yaml` — agent template for mode-aware Markdown
  artifact reports.

## Validate and package

```sh
archastro validate solution .
archastro package solution .
```

## Install and configure

The commands below require `archastro`, `jq`, `gh`, and `openssl`. Run them
while authenticated to the app that should receive the test results. The
installer must be allowed to import Solutions, install agents and automations,
manage the destination team, and create webhooks.

### 1. Choose the destination

Use one dedicated internal team. Do not reuse the reporter across multiple
teams: the signed payload supplies `team_id`, so the reporter's single team
membership is the destination allowlist.

```sh
export TEAM_ID="tem_replace_me"
export GITHUB_REPOSITORY="your-org/your-test-repo"

# Confirm that this is the intended internal destination before continuing.
archastro describe team "$TEAM_ID"
```

### 2. Import the Solution

After this sample is released to the catalog, import by slug:

```sh
archastro import solution shared-test-suite --team "$TEAM_ID"
```

To test from a local checkout before release, point the CLI at the catalog
repository root and still import by slug:

```sh
export ARCHASTRO_SAMPLES_DIR="$(git rev-parse --show-toplevel)"
archastro import solution shared-test-suite --team "$TEAM_ID"
```

Run that command from the `archagents` checkout so the exported root contains
`solutions/shared-test-suite`. Either import path uploads the workflow and
custom-object schemas before importing the templates. Confirm the imported
Solution is present:

```sh
archastro describe solution shared-test-suite-solution
```

### 3. Install the reporter and automation

Install each template with a stable runtime lookup key, then capture its ID
from JSON output:

```sh
REPORTER_ID="$(
  archastro --json install solution shared-test-suite-solution \
    --template shared-test-suite-reporter \
    --team "$TEAM_ID" \
    --name "Test Reporter" \
    --lookup-key shared-test-suite-reporter \
  | jq -er '.id'
)"

AUTOMATION_ID="$(
  archastro --json install solution shared-test-suite-solution \
    --template shared-test-suite-ingest \
    --team "$TEAM_ID" \
    --name "Test Ingest" \
    --lookup-key shared-test-suite-ingest \
  | jq -er '.id'
)"

printf 'Reporter: %s\nAutomation: %s\n' "$REPORTER_ID" "$AUTOMATION_ID"
```

### 4. Bind the internal destination

Add the reporter to the one destination team, then run the automation as that
agent. These are separate steps because a Solution import cannot choose a
runtime agent or team membership.

```sh
archastro create teammember \
  --team "$TEAM_ID" \
  --agent "$REPORTER_ID" \
  --role member

archastro update automation "$AUTOMATION_ID" \
  --run-as-agent "$REPORTER_ID"
```

### 5. Create the signed webhook

Generate a secret locally, create the generic webhook, and capture its public
URL. Do not print or commit the secret.

```sh
WEBHOOK_SECRET="$(openssl rand -hex 32)"
WEBHOOK_JSON="$(
  archastro --json create webhook \
    --lookup-key test-results \
    --signing-secret "$WEBHOOK_SECRET"
)"
WEBHOOK_ID="$(printf '%s' "$WEBHOOK_JSON" | jq -er '.id')"
WEBHOOK_URL="$(printf '%s' "$WEBHOOK_JSON" | jq -er '.webhook_url')"
```

Store the three runtime values as GitHub Actions secrets in the repository
that runs the tests:

```sh
gh secret set ARCHAGENTS_TEST_WEBHOOK_URL \
  --repo "$GITHUB_REPOSITORY" \
  --body "$WEBHOOK_URL"

gh secret set ARCHAGENTS_TEST_WEBHOOK_SECRET \
  --repo "$GITHUB_REPOSITORY" \
  --body "$WEBHOOK_SECRET"

gh secret set ARCHAGENTS_TEST_TEAM_ID \
  --repo "$GITHUB_REPOSITORY" \
  --body "$TEAM_ID"

unset WEBHOOK_SECRET WEBHOOK_JSON
```

### 6. Verify the installation

These read-only commands should resolve all installed resources and show Test
Ingest bound to the reporter:

```sh
archastro describe agent "$REPORTER_ID"
archastro describe automation "$AUTOMATION_ID"
archastro describe webhook "$WEBHOOK_ID"
archastro list agents --search shared-test-suite-reporter
archastro list automations --type trigger
```

Finally, add the workflow step from
[the GitHub Actions guide](docs/github-actions.md), run the test workflow, and
open the internal `tests:<suite_id>` thread. It should contain the deterministic
run summary, and Test Reporter should create the run and `latest` Markdown
artifacts.

## Current limitations

- Custom-object writes are best effort until the agent-created team
  custom-object authorization fix is available in the platform.
- Artifact creation is agent-routine driven; deterministic workflow thread
  messages are the reliable immediate signal.
- The package is internal-first. Sharing a network team is a deliberate later
  policy decision, not an install default. Do not reuse one reporter across
  multiple destination teams while `team_id` is payload-supplied.
