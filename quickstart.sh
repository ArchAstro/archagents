#!/usr/bin/env bash
# Deploy your first ArchAgent in 60 seconds.
#
# Usage:
#   ./quickstart.sh you@company.com
#
# What this does:
#   1. Checks for the archagent CLI (installs via Homebrew if missing)
#   2. Signs you in
#   3. Deploys the Onboarding Q&A agent (scripts + agent.yaml + seed FAQ)
#      via `archagent install agentsample onboarding-qa` — no files land
#      on your disk, the whole thing deploys in-memory from the release
#      tarball.
#   4. Asks the agent a question and prints the answer
#
# After this, try the other agents: `archagent install agentsample <slug>`
# or browse agents/<slug>/README.md for per-sample setup details.

set -euo pipefail

# --- Colors ---
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[32m'
CYAN='\033[36m'
RESET='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}→ $1${RESET}"; }
ok()   { echo -e "  ${GREEN}✓ $1${RESET}"; }

# --- Preflight ---
EMAIL="${1:-}"
if [[ -z "$EMAIL" ]]; then
  echo "Usage: ./quickstart.sh you@company.com"
  exit 1
fi

# --- Step 1: CLI ---
step "Checking for archagent CLI..."
if command -v archagent &>/dev/null; then
  ok "archagent $(archagent --version) found"
else
  step "Installing archagent via Homebrew..."
  brew install ArchAstro/tools/archagent
  ok "Installed archagent $(archagent --version)"
fi

# --- Step 2: Auth ---
step "Signing in as $EMAIL..."
archagent auth login "$EMAIL"
ok "Authenticated"

# --- Step 3: Deploy ---
step "Deploying Onboarding Q&A agent..."
archagent install agentsample onboarding-qa
ok "Agent deployed (agent.yaml + sample FAQ knowledge seeded)"

# --- Step 4: Test ---
step "Testing the agent..."
AGENT_ID=$(archagent list agents --search "onboarding" -o json 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); items=d if isinstance(d,list) else d.get('data',[]); print(items[0]['id'])" 2>/dev/null || echo "")

if [[ -n "$AGENT_ID" ]]; then
  SESSION_ID=$(archagent create agentsession --agent "$AGENT_ID" \
    --instructions "Answer new-hire questions from the knowledge base. Be helpful and concise." 2>&1 \
    | grep -oE 'ase_[A-Za-z0-9]+' | head -1)

  if [[ -n "$SESSION_ID" ]]; then
    echo ""
    echo -e "${DIM}Asking: \"What's the PTO policy?\"${RESET}"
    echo ""
    archagent exec agentsession "$SESSION_ID" -m "What's the PTO policy?" -w --timeout 60 2>&1 | tail -15
  fi
fi

# --- Done ---
echo ""
echo -e "${BOLD}${GREEN}Done!${RESET} Your first agent is live."
echo ""
echo -e "Try another sample:"
echo -e "  ${CYAN}archagent install agentsample code-review-agent${RESET}     — review every PR automatically"
echo -e "  ${CYAN}archagent install agentsample security-triage-agent${RESET} — daily vulnerability scans"
echo -e "  ${CYAN}archagent install agentsample threat-intel-agent${RESET}    — daily security brief"
echo ""
echo -e "Browse the full catalog with ${BOLD}archagent list agentsamples${RESET} — each sample's ${BOLD}README.md${RESET} has setup details."
