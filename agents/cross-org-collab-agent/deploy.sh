#!/usr/bin/env bash
# Deploy the Cross-Org Collaboration Agent
set -euo pipefail

cd "$(dirname "$0")"

# Resolve which CLI binary to invoke (archastro vs archagent). Order:
#   1. $ARCHASTRO_CLI env override
#   2. Nearest archastro.json / archagent.json walking up from here
#   3. First of archastro / archagent on PATH
#   4. Fallback: archagent
if [[ -n "${ARCHASTRO_CLI:-}" ]]; then
  CLI="$ARCHASTRO_CLI"
else
  CLI=""
  _dir="$PWD"
  while [[ -n "$_dir" && "$_dir" != "/" ]]; do
    if [[ -f "$_dir/archastro.json" ]]; then CLI="archastro"; break; fi
    if [[ -f "$_dir/archagent.json" ]]; then CLI="archagent"; break; fi
    _dir="$(dirname "$_dir")"
  done
  unset _dir
  if [[ -z "$CLI" ]]; then
    if   command -v archastro >/dev/null 2>&1; then CLI="archastro"
    elif command -v archagent >/dev/null 2>&1; then CLI="archagent"
    else CLI="archagent"
    fi
  fi
fi

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
    --name "$(echo "$name" | tr '-' ' ')" \
    --file "$script" 2>/dev/null || \
  "$CLI" update scripts "$name" --file "$script"
done

echo "🛡️  Deploying field guard schema..."
SCHEMA_ID=$("$CLI" create configs -f schemas/cross-org-hardened.yaml 2>&1 | grep -oE 'cfg_[A-Za-z0-9]+' | head -1) || \
SCHEMA_ID=$("$CLI" update configs -f schemas/cross-org-hardened.yaml 2>&1 | grep -oE 'cfg_[A-Za-z0-9]+' | head -1)
echo "  → schema: $SCHEMA_ID"

if [[ -z "$SCHEMA_ID" ]]; then
  echo "❌ Failed to deploy field guard schema. The agent WILL NOT have privacy guards without it."
  echo "   Fix the schema deployment and re-run: $CLI create configs -f schemas/cross-org-hardened.yaml"
  exit 1
fi

echo "🤖 Deploying agent..."
"$CLI" deploy agent agent.yaml

# Attach the schema to the participate routine
echo "🔗 Attaching schema to participate routine..."
ROUTINE_ID=$("$CLI" list agentroutines --agent cross-org-collab-agent -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print(r['id']) for r in d['data'] if r['name']=='Participate in conversations']" | head -1)

if [[ -n "$ROUTINE_ID" && -n "$SCHEMA_ID" ]]; then
  "$CLI" update agentroutines "$ROUTINE_ID" --preset-template-ids "$SCHEMA_ID"
  echo "  → routine $ROUTINE_ID now uses schema $SCHEMA_ID"
fi

echo "✅ Done. The Cross-Org Collaboration Agent is live."
echo ""
echo "Next steps:"
echo "  1. Add this agent to a cross-org team in the agent network"
echo "  2. Start a thread — the agent will participate with field guards enforced"
echo "  3. Try sending it a leak-attempt message to verify the guards reject it"
