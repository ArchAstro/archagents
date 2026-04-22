#!/usr/bin/env bash
# Deploy the Code Review Agent to your ArchAgents app.
#
# Prerequisites:
#   - archastro (or archagent) CLI installed and authenticated
#   - .env file populated (copy from env.example)
#   - GITHUB_TOKEN set as an org env var on the platform
#
# Usage:  ./deploy.sh

set -euo pipefail

cd "$(dirname "$0")"

# shellcheck disable=SC1091
source ./detect_cli_env.sh

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
  "$CLI" create scripts \
    --id "$name" \
    --name "$(echo "$name" | tr '-' ' ' | sed -E 's/(^|[[:space:]])./\U&/g')" \
    --file "$script" 2>/dev/null || \
  "$CLI" update scripts "$name" --file "$script"
done

echo "🤖 Deploying agent..."
"$CLI" deploy agent agent.yaml

echo "✅ Done. The Code Review Agent is live."
echo ""
echo "Next steps:"
echo "  1. Install the ArchAstro GitHub App on your repo"
echo "  2. Open a PR and watch the agent review it"
echo "  3. Customize the identity prompt in agent.yaml for your team's voice"
