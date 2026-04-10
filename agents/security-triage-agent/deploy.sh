#!/usr/bin/env bash
# Deploy the Security Triage Agent
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

echo "✅ Done. The Security Triage Agent is live."
echo ""
echo "Next steps:"
echo "  1. Upload your security policies (see ./scripts/upload-policies.sh)"
echo "  2. Wait for the daily-dependency-scan cron at 08:00 UTC"
echo "  3. Or trigger it manually via the portal"
