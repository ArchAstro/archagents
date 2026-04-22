#!/usr/bin/env bash
# Deploy the Security Triage Agent
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

echo "🤖 Deploying agent..."
"$CLI" deploy agent agent.yaml

echo "✅ Done. The Security Triage Agent is live."
echo ""
echo "Next steps:"
echo "  1. Upload your security policies (see ./scripts/upload-policies.sh)"
echo "  2. Wait for the daily-dependency-scan cron at 08:00 UTC"
echo "  3. Or trigger it manually via the portal"
