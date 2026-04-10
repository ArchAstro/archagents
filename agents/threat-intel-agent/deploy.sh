#!/usr/bin/env bash
# Deploy the Threat Intelligence Agent
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "❌ .env file not found. Copy env.example to .env and fill in your values."
  exit 1
fi

# shellcheck disable=SC1091
source .env

echo "📜 Deploying scripts..."
for script in scripts/*.aascript; do
  name=$(basename "$script" .aascript | tr '_' '-')
  echo "  → $name"
  archagent create scripts \
    --id "$name" \
    --name "$(echo "$name" | tr '-' ' ')" \
    --file "$script" 2>/dev/null || \
  archagent update scripts "$name" --file "$script"
done

echo "🤖 Deploying agent..."
archagent deploy agent agent.yaml

echo "✅ Done. The Threat Intelligence Agent is live."
echo ""
echo "Tomorrow at 07:00 UTC the agent will produce its first brief."
echo "To trigger it now, invoke the daily-threat-brief routine via the portal."
