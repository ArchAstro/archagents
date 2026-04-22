# Shared helper: resolves the CLI binary for ArchAgents / ArchAstro samples.
#
# Sets $CLI to "archastro" or "archagent" using this order (first match wins):
#   1. $ARCHASTRO_CLI env var (explicit override)
#   2. Walk up from this file's dir looking for archastro.json or archagent.json
#      (the project marker file written by `<cli> init`)
#   3. First of (archastro, archagent) found on $PATH
#   4. Fall back to "archagent"
#
# This file is copied identically into every sample directory — the CLI's
# `install agentsample` command copies only the sample's own subtree, so a
# single top-level helper would not be delivered. Keep the copies in sync.
#
# Source from a sibling script (after cd'ing into the sample dir):
#   source ./detect_cli_env.sh
#   "$CLI" deploy agent agent.yaml

__archastro_detect_from_project() {
  local dir="$1"
  while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ -f "$dir/archastro.json" ]]; then
      printf '%s' "archastro"
      return 0
    fi
    if [[ -f "$dir/archagent.json" ]]; then
      printf '%s' "archagent"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

__archastro_detect_from_path() {
  if command -v archastro >/dev/null 2>&1; then
    printf '%s' "archastro"
    return 0
  fi
  if command -v archagent >/dev/null 2>&1; then
    printf '%s' "archagent"
    return 0
  fi
  return 1
}

if [[ -n "${ARCHASTRO_CLI:-}" ]]; then
  CLI="$ARCHASTRO_CLI"
else
  __archastro_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if __archastro_found="$(__archastro_detect_from_project "$__archastro_here")"; then
    CLI="$__archastro_found"
  elif __archastro_found="$(__archastro_detect_from_path)"; then
    CLI="$__archastro_found"
  else
    CLI="archagent"
  fi
  unset __archastro_here __archastro_found
fi

unset -f __archastro_detect_from_project __archastro_detect_from_path
export CLI
