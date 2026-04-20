#!/usr/bin/env bash
# Deploy the ArchAgents FDE agent.
#
# Prerequisites:
#   - archagent CLI installed and authenticated (see install / auth skills)
#   - .env file populated (copy from env.example)
#
# This script:
#   1. Deploys the Script configs (custom tools)
#   2. Publishes each bundled skill from skills/<slug>/SKILL.md
#   3. Deploys the AgentTemplate (its `skills:` block references each
#      slug via config_ref — publishing skills FIRST is required for
#      config_ref resolution during agent provisioning)
#   4. Prints the impersonate commands so the customer can install
#      the FDE skill set into Claude Code, Codex, or OpenCode.
#
# Usage:  ./deploy.sh

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "❌ .env file not found. Copy env.example to .env if you need custom values."
  echo "   (The FDE agent ships with no required env vars, so .env is optional.)"
else
  # shellcheck disable=SC1091
  source .env
fi

echo "📜 Deploying scripts..."
for script in scripts/*.aascript; do
  name=$(basename "$script" .aascript)
  pretty="$(echo "$name" | tr '-' ' ')"
  echo "  → $name"
  archagent create scripts \
    --id "$name" \
    --name "$pretty" \
    --file "$script" 2>/dev/null || \
  archagent update scripts "$name" --file "$script"
done

echo "📚 Publishing skills..."
# Skills must be published BEFORE `deploy agent` so the agent template's
# `skills:` block can resolve each `config_ref` to a concrete config_id
# during agent provisioning.
for skill_dir in skills/*/; do
  slug=$(basename "$skill_dir")
  skill_md="$skill_dir/SKILL.md"
  if [[ ! -f "$skill_md" ]]; then
    echo "  ⚠ $slug: no SKILL.md, skipping"
    continue
  fi

  # Pull name and description from YAML frontmatter
  name=$(awk '/^---$/{f++;next} f==1 && /^name:/{sub(/^name:[[:space:]]*/,""); print; exit}' "$skill_md")
  desc=$(awk '/^---$/{f++;next} f==1 && /^description:/{sub(/^description:[[:space:]]*/,""); print; exit}' "$skill_md")
  name="${name:-$slug}"
  desc="${desc:-Skill: $slug}"

  echo "  → $slug"
  archagent create skill \
    -n "$name" \
    -d "$desc" \
    -s "$slug" \
    --file "$skill_md" 2>/dev/null || \
  archagent update skillfile "$slug" SKILL.md --file "$skill_md"

  # Publish supporting reference files (if any)
  while IFS= read -r -d '' f; do
    rel="${f#$skill_dir}"
    if [[ "$rel" == "SKILL.md" ]]; then continue; fi
    echo "      · $rel"
    archagent create skillfile "$slug" "$rel" --file "$f" 2>/dev/null || \
    archagent update skillfile "$slug" "$rel" --file "$f"
  done < <(find "$skill_dir" -type f -print0)
done

echo "🤖 Deploying agent..."
archagent deploy agent agent.yaml

echo ""
echo "✅ ArchAgents FDE agent deployed."
echo ""
echo "Next steps:"
echo ""
echo "  1. Open a thread with the agent:"
echo "       archagent create agentsession \\"
echo "         --agent archagent-fde \\"
echo "         --instructions \"Help me deploy my first agent.\" \\"
echo "         --wait"
echo ""
echo "  2. OR impersonate it into your coding harness:"
echo "       archagent impersonate start archagent-fde"
echo "       archagent impersonate list skills"
echo "       archagent impersonate install skill <skill-id> --harness claude"
echo "       archagent impersonate install skill <skill-id> --harness codex"
echo "       archagent impersonate install skill <skill-id> --harness opencode"
echo ""
echo "     This installs the FDE's skills into your local .claude/ .codex/ or .opencode/"
echo "     directory — turning your coding harness into an ArchAgents FDE."
