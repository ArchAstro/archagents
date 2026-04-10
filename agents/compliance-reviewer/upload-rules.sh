#!/usr/bin/env bash
# Upload compliance rule markdown files to the agent's knowledge base.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <rule1.md> [rule2.md] ..."
  exit 1
fi

cd "$(dirname "$0")"

INSTALLATION_ID=$(archagent list agentinstallations --agent compliance-reviewer -o json 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d['data'] if i['kind']=='archastro/files']" \
  | head -1)

if [[ -z "$INSTALLATION_ID" ]]; then
  echo "❌ Could not find archastro/files installation. Did you run ./deploy.sh first?"
  exit 1
fi

for file in "$@"; do
  filename=$(basename "$file")
  echo "📤 $filename"
  data=$(base64 -i "$file" | tr -d '\n')

  file_id=$(archagent create files \
    --data "$data" \
    --filename "$filename" \
    --content-type "text/markdown" 2>&1 \
    | grep -oE 'fil_[A-Za-z0-9]+' | head -1)

  archagent create agentinstallationsources \
    --installation "$INSTALLATION_ID" \
    --type file/document \
    --payload "{\"file_id\": \"$file_id\"}" 2>&1 | head -1
done

echo "✅ Done."
