#!/usr/bin/env bash
# Deploy the Cross-Org Collaboration Agent
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

echo "🛡️  Deploying field guard schema..."
SCHEMA_ID=$(archagent create configs -f schemas/cross-org-hardened.yaml 2>&1 | grep -oE 'cfg_[A-Za-z0-9]+' | head -1) || \
SCHEMA_ID=$(archagent update configs -f schemas/cross-org-hardened.yaml 2>&1 | grep -oE 'cfg_[A-Za-z0-9]+' | head -1)
echo "  → schema: $SCHEMA_ID"

if [[ -z "$SCHEMA_ID" ]]; then
  echo "❌ Failed to deploy field guard schema. The agent WILL NOT have privacy guards without it."
  echo "   Fix the schema deployment and re-run: archagent create configs -f schemas/cross-org-hardened.yaml"
  exit 1
fi

echo "🤖 Deploying agent..."
archagent deploy agent agent.yaml

# Attach the schema to the participate routine
echo "🔗 Attaching schema to participate routine..."
ROUTINE_ID=$(archagent list agentroutines --agent cross-org-collab-agent -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print(r['id']) for r in d['data'] if r['name']=='Participate in conversations']" | head -1)

if [[ -n "$ROUTINE_ID" && -n "$SCHEMA_ID" ]]; then
  archagent update agentroutines "$ROUTINE_ID" --preset-template-ids "$SCHEMA_ID"
  echo "  → routine $ROUTINE_ID now uses schema $SCHEMA_ID"
fi

echo "✅ Done. The Cross-Org Collaboration Agent is live."
echo ""
echo "Next steps:"
echo "  1. Add this agent to a cross-org team in the agent network"
echo "  2. Start a thread — the agent will participate with field guards enforced"
echo "  3. Try sending it a leak-attempt message to verify the guards reject it"
