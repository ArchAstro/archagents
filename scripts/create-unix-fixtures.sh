#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR=""
VERSION="0.3.1"
PLATFORM=""
ARCH_LABEL=""
BINARY_NAME="archagent"

usage() {
  cat <<'EOF'
Usage: create-unix-fixtures.sh --output-dir <dir> [--version <version>] [--platform <darwin|linux>] [--arch-label <x64|arm64|x64-musl>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --arch-label)
      ARCH_LABEL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
  echo "--output-dir is required" >&2
  exit 1
fi

if [[ -z "$PLATFORM" ]]; then
  case "$(uname -s)" in
    Darwin) PLATFORM="darwin" ;;
    Linux) PLATFORM="linux" ;;
    *)
      echo "Unsupported platform" >&2
      exit 1
      ;;
  esac
fi

if [[ -z "$ARCH_LABEL" ]]; then
  case "$(uname -m)" in
    x86_64|amd64) ARCH_LABEL="x64" ;;
    arm64|aarch64) ARCH_LABEL="arm64" ;;
    *)
      echo "Unsupported architecture" >&2
      exit 1
      ;;
  esac
fi

mkdir -p "$OUTPUT_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PAYLOAD_DIR="$TMP_DIR/payload"
mkdir -p "$PAYLOAD_DIR"

cat >"$PAYLOAD_DIR/$BINARY_NAME" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ "\${1:-}" == "--version" || "\${1:-}" == "version" ]]; then
  echo "$VERSION"
  exit 0
fi
if [[ "\${1:-}" == "completion" ]]; then
  case "\${2:-}" in
    bash)
      echo 'complete -W "--version completion" archagent'
      ;;
    zsh)
      echo '#compdef archagent'
      ;;
    fish)
      echo 'complete -c archagent -l version'
      ;;
    *)
      echo "unknown shell" >&2
      exit 1
      ;;
  esac
  exit 0
fi
echo "archagent fixture"
EOF
chmod +x "$PAYLOAD_DIR/$BINARY_NAME"

ASSET_NAME="${BINARY_NAME}-${PLATFORM}-${ARCH_LABEL}.tar.gz"
tar -czf "$OUTPUT_DIR/$ASSET_NAME" -C "$PAYLOAD_DIR" "$BINARY_NAME"

CHECKSUM_FILE="$OUTPUT_DIR/SHA256SUMS"
if command -v sha256sum >/dev/null 2>&1; then
  CHECKSUM="$(sha256sum "$OUTPUT_DIR/$ASSET_NAME" | awk '{print $1}')"
else
  CHECKSUM="$(shasum -a 256 "$OUTPUT_DIR/$ASSET_NAME" | awk '{print $1}')"
fi
printf '%s  %s\n' "$CHECKSUM" "$ASSET_NAME" >"$CHECKSUM_FILE"
