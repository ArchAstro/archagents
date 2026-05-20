# Hourly Log Analysis

Scan GCP logs for security anomalies

Standalone routine. Attach to any existing agent in your org to schedule it on that agent's cadence.

## Setup

- **`GCLOUD_PROJECT_ID`** — GCP project id with Cloud Logging enabled.
- **`GCLOUD_SA_KEY`** — Service account JSON with `logging.viewer` (read-only). The
