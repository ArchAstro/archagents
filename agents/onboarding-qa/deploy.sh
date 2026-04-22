#!/usr/bin/env bash
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
