#!/usr/bin/env bash
# Local mirror of .github/workflows/release-samples.yml — packs every
# sample under agents/ and solutions/ into
# ./releases/<root>/<slug>-<version>.tar.gz (where <root> is `agents`
# or `solutions`). The split lets downstream tools (e.g. local
# importers) pull only Solution bundles without needing to peek inside
# every tarball to filter out agent-mode samples that don't have a
# `deploy_solution` step.
#
# Use this to:
#   - smoke-test the catalog flow locally with
#     `archagent import solution ./releases/<root>/<slug>-<version>.tar.gz`,
#   - regenerate every tarball after a version-bump sweep,
#   - confirm `pack` is green across the whole catalog before pushing.
#
# Usage:
#   scripts/build-releases.sh
#   scripts/build-releases.sh --output-dir dist/
#   scripts/build-releases.sh --only security-triage-agent-sample
#   scripts/build-releases.sh --clean        # rm tarballs before rebuilding
#   scripts/build-releases.sh --skip-existing  # don't rebuild if file is present
#
# Exit codes:
#   0 — all samples packed successfully (or skipped via --skip-existing)
#   1 — usage / arg error
#   non-zero — `archagent package solution` failed for at least one sample

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
OUTPUT_DIR="${REPO_ROOT}/releases"
ONLY_SLUG=""
CLEAN=0
SKIP_EXISTING=0

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-dir=*)
      OUTPUT_DIR="${1#*=}"
      shift
      ;;
    --only)
      ONLY_SLUG="$2"
      shift 2
      ;;
    --only=*)
      ONLY_SLUG="${1#*=}"
      shift
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    --skip-existing)
      SKIP_EXISTING=1
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      usage 1
      ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

if [[ "$CLEAN" -eq 1 ]]; then
  # Only touch *.tar.gz so this can't accidentally nuke unrelated
  # files if the user passed `--output-dir .` or similar. Sweeps the
  # root + the per-root subdirs (`agents/`, `solutions/`) because the
  # layout switched from flat to nested.
  find "$OUTPUT_DIR" -maxdepth 2 -name "*.tar.gz" -delete
fi

cd "$REPO_ROOT"

declare -a PLAN=()
# Catalog roots: agents/ (agent-mode samples) + solutions/ (Solution bundles).
for root in agents solutions; do
  [[ -d "$root" ]] || continue
  for sample_dir in "$root"/*/; do
    [[ -d "$sample_dir" ]] || continue
    [[ -f "$sample_dir/sample.yaml" ]] || continue
    slug=$(basename "$sample_dir")
    if [[ -n "$ONLY_SLUG" && "$slug" != "$ONLY_SLUG" ]]; then
      continue
    fi
    PLAN+=("$root/$slug")
  done
done

if [[ ${#PLAN[@]} -eq 0 ]]; then
  if [[ -n "$ONLY_SLUG" ]]; then
    echo "no sample matched --only ${ONLY_SLUG}" >&2
    exit 1
  fi
  echo "no samples found under agents/ or solutions/" >&2
  exit 1
fi

packed=0
skipped=0
failed=0

for sample_path in "${PLAN[@]}"; do
  slug=$(basename "$sample_path")
  # $sample_path is always `<root>/<slug>` (PLAN is populated that way
  # above), so dirname gives back `agents` or `solutions` — the
  # destination subdir under $OUTPUT_DIR.
  root=$(dirname "$sample_path")
  target_dir="$OUTPUT_DIR/$root"
  # Read version from sample.yaml without pulling in PyYAML for a
  # one-line lookup — sample.yaml is line-oriented and the validator
  # already rejects anything that wouldn't match this regex.
  version=$(awk '/^version:[[:space:]]*v[0-9]+\.[0-9]+\.[0-9]+/ {print $2; exit}' "$sample_path/sample.yaml")
  if [[ -z "$version" ]]; then
    echo "✗ $sample_path: could not read version from sample.yaml" >&2
    failed=$((failed + 1))
    continue
  fi
  tarball="$target_dir/${slug}-${version}.tar.gz"
  if [[ "$SKIP_EXISTING" -eq 1 && -f "$tarball" ]]; then
    echo "✓ $sample_path → already at ${tarball#$REPO_ROOT/} (skipping)"
    skipped=$((skipped + 1))
    continue
  fi

  echo "→ $sample_path → ${tarball#$REPO_ROOT/}"
  if archagent package solution "$sample_path" --output-dir "$target_dir" >/dev/null; then
    packed=$((packed + 1))
  else
    echo "✗ $sample_path: pack failed" >&2
    failed=$((failed + 1))
  fi
done

echo
echo "packed=$packed skipped=$skipped failed=$failed → $OUTPUT_DIR/"

exit $((failed == 0 ? 0 : 2))
