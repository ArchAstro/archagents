# GitHub Actions setup

This guide sends normalized JUnit results to the Shared Test Suite Solution.
The automation expects a generic webhook event named `test_run`, which the
platform normalizes to `webhook.external.test_run`.

## 1. Create a signed generic webhook

Create the webhook in the app where the Solution was imported. Keep the
secret out of source control:

```sh
WEBHOOK_SECRET="$(openssl rand -hex 32)"
archastro create webhook --lookup-key test-results --signing-secret "$WEBHOOK_SECRET"
```

Record the returned webhook URL. Then add these GitHub repository secrets:

| Secret | Value |
| --- | --- |
| `ARCHAGENTS_TEST_WEBHOOK_URL` | Returned generic webhook URL |
| `ARCHAGENTS_TEST_WEBHOOK_SECRET` | `WEBHOOK_SECRET` from the command above |
| `ARCHAGENTS_TEST_TEAM_ID` | The single internal team that owns the `tests:<suite_id>` thread |

Use a dedicated Test Reporter agent that belongs only to this destination
team. The signed payload selects `team_id`; limiting the reporter to one team
turns team membership into the destination allowlist and prevents a webhook
sender from redirecting test details to another team.

## 2. Post a test result from GitHub Actions

Run the test command in a step that still runs after failures so its JUnit
file is available. The example below parses standard JUnit XML and posts at
most 100 results. Adapt the parser if your runner emits a different format.

```yaml
- name: Publish TestRun to ArchAgents
  if: always()
  env:
    WEBHOOK_URL: ${{ secrets.ARCHAGENTS_TEST_WEBHOOK_URL }}
    WEBHOOK_SECRET: ${{ secrets.ARCHAGENTS_TEST_WEBHOOK_SECRET }}
    TEAM_ID: ${{ secrets.ARCHAGENTS_TEST_TEAM_ID }}
    SUITE_ID: stripe-paper
  run: |
    python3 - <<'PY' > test-run.json
    import json, os, re, xml.etree.ElementTree as ET

    def identifier(value, fallback):
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip(".-_")
        return (normalized or fallback)[:200]

    root = ET.parse("results.xml").getroot()
    results = []
    counts = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

    for case in root.iter("testcase"):
        counts["total"] += 1
        raw_test_key = ".".join(filter(None, [case.get("classname"), case.get("name", "unknown")]))
        test_key = identifier(raw_test_key, "unknown")
        duration_ms = int(float(case.get("time", "0")) * 1000)
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        skipped = case.find("skipped")

        if failure is not None:
            counts["failed"] += 1
            results.append({
                "test_key": test_key,
                "status": "fail",
                "duration_ms": duration_ms,
                "error": ((failure.get("message") or "") + "\n" + (failure.text or ""))[:2000],
            })
        elif skipped is not None:
            counts["skipped"] += 1
            results.append({"test_key": test_key, "status": "skip", "duration_ms": duration_ms})
        else:
            counts["passed"] += 1
            results.append({"test_key": test_key, "status": "pass", "duration_ms": duration_ms})

    mode = os.environ.get("TEST_MODE")
    if not mode:
        mode = "single" if counts["total"] == 1 else "batch" if counts["total"] <= 10 else "suite"

    # Namespace run IDs by repository so separate repositories cannot collide
    # when they happen to use the same CI run number.
    repository = os.environ.get("GITHUB_REPOSITORY", "unknown-repository")
    namespaced_run_id = identifier(f"{repository}-{os.environ['GITHUB_RUN_ID']}", "unknown-run")

    payload = {
        "event_type": "test_run",
        "suite_id": identifier(os.environ["SUITE_ID"], "ad-hoc"),
        "run_id": namespaced_run_id,
        "mode": mode,
        "sha": os.environ.get("GITHUB_SHA", ""),
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "conclusion": "failure" if counts["failed"] else "success",
        "stats": counts,
        "results": results[:100],
        "run_url": f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "repository": repository,
        "team_id": os.environ["TEAM_ID"],
    }
    print(json.dumps(payload, separators=(",", ":")))
    PY

    SIGNATURE="$(openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex < test-run.json | sed 's/^.* //')"
    curl --fail-with-body --request POST "$WEBHOOK_URL" \
      --header 'Content-Type: application/json' \
      --header 'X-Event-Type: test_run' \
      --header "X-Webhook-Signature: $SIGNATURE" \
      --data-binary @test-run.json
```

## Payload contract

Required top-level fields:

```json
{
  "event_type": "test_run",
  "suite_id": "stripe-paper",
  "run_id": "123456",
  "conclusion": "success",
  "team_id": "tem_..."
}
```

Optional fields include `mode`, `test_keys`, `sha`, `branch`, `stats`,
`results`, `run_url`, and `repository`. IDs are normalized before storage;
namespace `run_id` by repository and keep suite/test IDs stable so distinct
runs do not collapse to the same normalized key.

### Modes and routing

| Mode | Meaning | Route when `suite_id` is present |
| --- | --- | --- |
| `suite` | Full suite | `tests:<suite_id>` |
| `single` | One selected test | `tests:<suite_id>` |
| `batch` | Selected subset | `tests:<suite_id>` |
| `ad-hoc` | No formal suite | `tests:ad-hoc` |

Set `mode` explicitly when possible. Otherwise the workflow infers `single`
for one result, `batch` for 2–10 results with a suite, and `suite` for larger
suite-scoped runs. Runs without a suite default to `ad-hoc`.

## 3. Verify

After one test run, open the internal team thread named `tests:<suite_id>`.
It should contain the run summary and failures, and the Test Reporter should
create a Markdown artifact for the run.

If no message appears, verify the generic webhook dispatch prerequisite is
deployed, that Test Ingest has its runtime reporter in `run_as_agent`, and
that the dedicated reporter agent belongs to the payload's `team_id` and no
other destination team.
