#!/usr/bin/env bash
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

echo "✅ Done. The Release Notes Bot is live."
echo ""
echo "Next Monday at 10:00 UTC the bot will draft your first changelog."
echo "To trigger now, invoke the weekly-release-notes routine via the portal."
