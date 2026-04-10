#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "🤖 Deploying Onboarding Q&A agent..."
archagent deploy agent agent.yaml

echo "✅ Done."
echo ""
echo "Next steps:"
echo "  1. Upload knowledge: ./upload-knowledge.sh /path/to/handbook.pdf ..."
echo "  2. Add the agent to a thread or Slack channel"
echo "  3. Ask it questions"
