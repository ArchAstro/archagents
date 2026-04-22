#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# shellcheck disable=SC1091
source ./detect_cli_env.sh

echo "🤖 Deploying Onboarding Q&A agent..."
"$CLI" deploy agent agent.yaml

if [[ -f knowledge/sample-faq.md ]]; then
  echo "📚 Uploading sample FAQ..."
  ./upload-knowledge.sh knowledge/sample-faq.md
fi

echo "✅ Done."
echo ""
echo "Next steps:"
echo "  1. Upload knowledge: ./upload-knowledge.sh /path/to/handbook.pdf ..."
echo "  2. Add the agent to a thread or Slack channel"
echo "  3. Ask it questions"
