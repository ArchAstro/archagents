#!/usr/bin/env bash
# Import your first ArchAgents sample Solution.
#
# Usage:
#   ./quickstart.sh you@company.com
#
# What this does:
#   1. Checks for the archagent CLI (installs via Homebrew if missing)
#   2. Signs you in
#   3. Imports the Onboarding Q&A sample Solution via
#      `archagent install agentsample onboarding-qa-sample` — no files
#      land on your disk, the whole bundle imports in-memory from the
#      release tarball.
#   4. Shows where to install the imported AgentTemplate.
#
# After this, try the other sample Solutions:
# `archagent install agentsample <slug>-sample` or browse
# solutions/<slug>-sample/README.md for per-sample setup details.

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

# --- Step 3: Import ---
step "Importing Onboarding Q&A sample Solution..."
archagent install agentsample onboarding-qa-sample
ok "Solution imported (AgentTemplate + setup actions)"

# --- Done ---
echo ""
echo -e "${BOLD}${GREEN}Done!${RESET} Your first sample Solution is imported."
echo ""
echo -e "Install the imported AgentTemplate from the catalog, then finish its setup actions."
echo ""
echo -e "Try another sample Solution:"
echo -e "  ${CYAN}archagent install agentsample code-review-agent-sample${RESET}     — review every PR automatically"
echo -e "  ${CYAN}archagent install agentsample security-triage-agent-sample${RESET} — daily vulnerability scans"
echo -e "  ${CYAN}archagent install agentsample threat-intel-agent-sample${RESET}    — daily security brief"
echo ""
echo -e "Browse the full catalog with ${BOLD}archagent list agentsamples${RESET} — each Solution README has setup details."
