#!/usr/bin/env bash
# Upload compliance rule markdown files to the agent's knowledge base.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <rule1.md> [rule2.md] ..."
  exit 1
fi

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

INSTALLATION_ID=$("$CLI" list agentinstallations --agent compliance-reviewer -o json 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d['data'] if i['kind']=='archastro/files']" \
  | head -1)

if [[ -z "$INSTALLATION_ID" ]]; then
  echo "❌ Could not find archastro/files installation. Did you run ./deploy.sh first?"
  exit 1
fi

for file in "$@"; do
  filename=$(basename "$file")
  echo "📤 $filename"
  data=$(base64 < "$file" | tr -d '\n')

  file_id=$("$CLI" create files \
    --data "$data" \
    --filename "$filename" \
    --content-type "text/markdown" 2>&1 \
    | grep -oE 'fil_[A-Za-z0-9]+' | head -1)

  "$CLI" create agentinstallationsources \
    --installation "$INSTALLATION_ID" \
    --type file/document \
    --payload "{\"file_id\": \"$file_id\"}" 2>&1 | head -1
done

echo "✅ Done."
