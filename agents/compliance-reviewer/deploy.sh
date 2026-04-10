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

echo "📜 Uploading compliance rules..."
echo "   (waiting for installation to provision...)"
sleep 5
./upload-rules.sh rules/*.md || {
  echo "⚠️  Rule upload failed — the files installation may not be ready yet."
  echo "   Retry in a minute: ./upload-rules.sh rules/*.md"
}

echo "✅ Done."
echo ""
echo "Next steps:"
echo "  1. Install the GitHub App on your repo"
echo "  2. Open a PR — the agent will review against the rules"
