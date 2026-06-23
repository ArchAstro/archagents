#!/usr/bin/env bash
#
# Regression test for the default release-repo resolution in the installers.
#
# The installer-smoke-test workflow always sets ARCHAGENT_RELEASE_BASE_URL to a
# local fixture server, so it never exercises the GitHub URL that real users hit.
# That gap let install.sh ship pointing at a nonexistent repo (archagent-cli)
# while install.ps1 pointed at the correct one, 404ing every `curl | bash` install.
#
# These checks run install.sh's real --print-asset-url path with NO base-url
# override, assert it resolves to the repo that actually hosts the releases, and
# guard against the two installers drifting onto different repos again.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_SH="$ROOT_DIR/install.sh"
INSTALL_PS1="$ROOT_DIR/install.ps1"

# The GitHub repo that release CI publishes archagent-* assets to.
EXPECTED_REPO="archagents"
EXPECTED_OWNER="ArchAstro"

failures=0
fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}
pass() {
  echo "ok: $*"
}

# install.sh reads ARCHAGENT_RELEASE_BASE_URL and ARCHAGENT_VERSION from the
# environment; unset both so these checks exercise the real default GitHub
# resolution regardless of ambient state in the dev shell or CI runner.
resolve_default() {
  env -u ARCHAGENT_RELEASE_BASE_URL -u ARCHAGENT_VERSION "$INSTALL_SH" "$@"
}

# 1. Default `latest` resolution must point at the real release repo.
latest_url="$(resolve_default --print-asset-url)"
expected_latest_prefix="https://github.com/${EXPECTED_OWNER}/${EXPECTED_REPO}/releases/latest/download/"
if [[ "$latest_url" == "$expected_latest_prefix"* ]]; then
  pass "latest asset URL resolves to ${EXPECTED_OWNER}/${EXPECTED_REPO}"
else
  fail "latest asset URL should start with $expected_latest_prefix but was: $latest_url"
fi

# 2. Pinned-version resolution must point at the real release repo.
pinned_url="$(resolve_default --print-asset-url --version 0.3.1)"
expected_pinned_prefix="https://github.com/${EXPECTED_OWNER}/${EXPECTED_REPO}/releases/download/v0.3.1/"
if [[ "$pinned_url" == "$expected_pinned_prefix"* ]]; then
  pass "pinned asset URL resolves to ${EXPECTED_OWNER}/${EXPECTED_REPO}"
else
  fail "pinned asset URL should start with $expected_pinned_prefix but was: $pinned_url"
fi

# 3. install.sh and install.ps1 must each pin the canonical release repo, so
#    neither can drift independently and both are anchored to one source of
#    truth rather than only to each other.
sh_repo="$(grep -E '^REPO=' "$INSTALL_SH" | head -n1 | sed -E 's/^REPO="?([^"]*)"?.*/\1/')"
ps1_repo="$(grep -E '^\$Repo[[:space:]]*=' "$INSTALL_PS1" | head -n1 | sed -E 's/.*=[[:space:]]*"([^"]*)".*/\1/')"
if [[ "$sh_repo" == "$EXPECTED_REPO" ]]; then
  pass "install.sh REPO is $EXPECTED_REPO"
else
  fail "install.sh REPO should be $EXPECTED_REPO but was: '$sh_repo'"
fi
if [[ "$ps1_repo" == "$EXPECTED_REPO" ]]; then
  pass "install.ps1 \$Repo is $EXPECTED_REPO"
else
  fail "install.ps1 \$Repo should be $EXPECTED_REPO but was: '$ps1_repo'"
fi

if [[ "$failures" -gt 0 ]]; then
  echo "$failures check(s) failed" >&2
  exit 1
fi
echo "All installer URL checks passed"
