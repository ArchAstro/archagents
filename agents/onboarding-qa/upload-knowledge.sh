#!/usr/bin/env bash
# Upload one or more files to the Onboarding Q&A agent's knowledge base.
#
# Usage:
#   ./upload-knowledge.sh /path/to/handbook.pdf /path/to/setup.md
#
# Files are uploaded via `archagent create files` and then attached as
# ingestion sources to the agent's archastro/files installation.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <file1> [file2] ..."
  exit 1
fi

cd "$(dirname "$0")"

# Find the agent's archastro/files installation ID
INSTALLATION_ID=$(archagent list agentinstallations --agent onboarding-qa -o json 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d['data'] if i['kind']=='archastro/files']" \
  | head -1)

if [[ -z "$INSTALLATION_ID" ]]; then
  echo "❌ Could not find archastro/files installation. Did you run ./deploy.sh first?"
  exit 1
fi

echo "📁 Installation: $INSTALLATION_ID"

for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    echo "⚠️  $file not found, skipping"
    continue
  fi

  filename=$(basename "$file")
  echo ""
  echo "📤 Uploading $filename..."

  # 1. base64 the file
  data=$(base64 < "$file" | tr -d '\n')

  # 2. Detect content type
  case "$filename" in
    *.pdf)  content_type="application/pdf" ;;
    *.md)   content_type="text/markdown" ;;
    *.txt)  content_type="text/plain" ;;
    *.html) content_type="text/html" ;;
    *.docx) content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document" ;;
    *)      content_type="application/octet-stream" ;;
  esac

  # 3. Upload the file
  file_id=$(archagent create files \
    --data "$data" \
    --filename "$filename" \
    --content-type "$content_type" 2>&1 \
    | grep -oE 'fil_[A-Za-z0-9]+' | head -1)

  if [[ -z "$file_id" ]]; then
    echo "  ❌ Upload failed"
    continue
  fi

  echo "  → file: $file_id"

  # 4. Attach as ingestion source
  archagent create agentinstallationsources \
    --installation "$INSTALLATION_ID" \
    --type file/document \
    --payload "{\"file_id\": \"$file_id\"}" 2>&1 | head -1
done

echo ""
echo "✅ Done. The agent is indexing the new files. Search will work in ~30 seconds."
