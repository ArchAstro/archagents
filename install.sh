#!/usr/bin/env bash

set -euo pipefail

OWNER="ArchAstro"
REPO="archagent-cli"
BINARY_NAME="archagent"
DEFAULT_VERSION="latest"
INSTALL_DIR="${ARCHAGENT_INSTALL_DIR:-}"
REQUESTED_VERSION="${ARCHAGENT_VERSION:-$DEFAULT_VERSION}"
RELEASE_BASE_URL="${ARCHAGENT_RELEASE_BASE_URL:-}"
SYSTEM_INSTALL="false"
DRY_RUN="false"
PRINT_ASSET_URL="false"
SKIP_PATH_UPDATE="${ARCHAGENT_INSTALL_SKIP_PATH_UPDATE:-false}"
SKIP_COMPLETIONS="${ARCHAGENT_INSTALL_SKIP_COMPLETIONS:-false}"
SKIP_VERIFY="${ARCHAGENT_INSTALL_SKIP_VERIFY:-false}"

usage() {
  cat <<'EOF'
Usage: install.sh [--version <version>] [--install-dir <dir>] [--base-url <url>] [--system] [--dry-run] [--print-asset-url]

Options:
  --version <version>       Install a specific version (for example 0.3.1 or v0.3.1)
  --install-dir <dir>       Install into a specific directory
  --base-url <url>          Override the resolved release download base URL
  --system                  Install into /usr/local/bin
  --dry-run                 Print the resolved install plan without downloading
  --print-asset-url         Print only the resolved asset URL and exit
  -h, --help                Show help

Environment:
  ARCHAGENT_RELEASE_BASE_URL         Override the release base URL for tests or staging
  ARCHAGENT_INSTALL_SKIP_PATH_UPDATE Skip shell rc PATH changes when true
  ARCHAGENT_INSTALL_SKIP_COMPLETIONS Skip completion installation when true
  ARCHAGENT_INSTALL_SKIP_VERIFY      Skip archagent --version verification when true
EOF
}

normalize_bool() {
  local value="${1:-false}"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes|on) echo "true" ;;
    *) echo "false" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      REQUESTED_VERSION="$2"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --base-url)
      RELEASE_BASE_URL="$2"
      shift 2
      ;;
    --system)
      SYSTEM_INSTALL="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --print-asset-url)
      PRINT_ASSET_URL="true"
      shift
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

SKIP_PATH_UPDATE="$(normalize_bool "$SKIP_PATH_UPDATE")"
SKIP_COMPLETIONS="$(normalize_bool "$SKIP_COMPLETIONS")"
SKIP_VERIFY="$(normalize_bool "$SKIP_VERIFY")"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin)
    PLATFORM="darwin"
    ARCHIVE_EXT="tar.gz"
    ;;
  Linux)
    PLATFORM="linux"
    ARCHIVE_EXT="tar.gz"
    ;;
  *)
    echo "Unsupported operating system: $OS" >&2
    exit 1
    ;;
esac

case "$ARCH" in
  x86_64|amd64)
    ARCH_LABEL="x64"
    ;;
  arm64|aarch64)
    ARCH_LABEL="arm64"
    ;;
  *)
    echo "Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

if [[ "$PLATFORM" == "linux" && "$ARCH_LABEL" == "x64" ]]; then
  if command -v ldd >/dev/null 2>&1 && ldd --version 2>&1 | grep -qi "musl"; then
    ARCH_LABEL="x64-musl"
  fi
fi

if [[ -z "$INSTALL_DIR" ]]; then
  if [[ "$SYSTEM_INSTALL" == "true" ]]; then
    INSTALL_DIR="/usr/local/bin"
  elif [[ "$PLATFORM" == "darwin" ]]; then
    if [[ -d "/usr/local/bin" && -w "/usr/local/bin" ]] || [[ ! -d "/usr/local/bin" && -w "/usr/local" ]]; then
      INSTALL_DIR="/usr/local/bin"
    else
      INSTALL_DIR="$HOME/.local/bin"
    fi
  else
    INSTALL_DIR="$HOME/.local/bin"
  fi
fi

VERSION_TAG="$REQUESTED_VERSION"
if [[ "$VERSION_TAG" != "latest" && "$VERSION_TAG" != v* ]]; then
  VERSION_TAG="v$VERSION_TAG"
fi

ASSET_NAME="${BINARY_NAME}-${PLATFORM}-${ARCH_LABEL}.${ARCHIVE_EXT}"

if [[ -n "$RELEASE_BASE_URL" ]]; then
  RESOLVED_RELEASE_BASE_URL="${RELEASE_BASE_URL%/}"
elif [[ "$REQUESTED_VERSION" == "latest" ]]; then
  RESOLVED_RELEASE_BASE_URL="https://github.com/${OWNER}/${REPO}/releases/latest/download"
else
  RESOLVED_RELEASE_BASE_URL="https://github.com/${OWNER}/${REPO}/releases/download/${VERSION_TAG}"
fi

ASSET_URL="${RESOLVED_RELEASE_BASE_URL}/${ASSET_NAME}"
CHECKSUM_URL="${RESOLVED_RELEASE_BASE_URL}/SHA256SUMS"
TARGET_PATH="${INSTALL_DIR}/${BINARY_NAME}"

if [[ "$PRINT_ASSET_URL" == "true" ]]; then
  echo "$ASSET_URL"
  exit 0
fi

if [[ "$DRY_RUN" == "true" ]]; then
  cat <<EOF
version=${REQUESTED_VERSION}
platform=${PLATFORM}
arch=${ARCH_LABEL}
asset=${ASSET_NAME}
release_base_url=${RESOLVED_RELEASE_BASE_URL}
asset_url=${ASSET_URL}
checksum_url=${CHECKSUM_URL}
install_dir=${INSTALL_DIR}
target_path=${TARGET_PATH}
skip_path_update=${SKIP_PATH_UPDATE}
skip_completions=${SKIP_COMPLETIONS}
skip_verify=${SKIP_VERIFY}
EOF
  exit 0
fi

need_command curl
need_command tar
need_command mktemp
need_command install

mkdir -p "$INSTALL_DIR"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

ASSET_PATH="${TMP_DIR}/${ASSET_NAME}"
CHECKSUM_PATH="${TMP_DIR}/SHA256SUMS"
EXTRACT_DIR="${TMP_DIR}/extract"

echo "Downloading ${ASSET_NAME}"
curl -fsSL "$ASSET_URL" -o "$ASSET_PATH"

if curl -fsSL "$CHECKSUM_URL" -o "$CHECKSUM_PATH"; then
  echo "Verifying checksum"
  EXPECTED_LINE="$(grep " ${ASSET_NAME}\$" "$CHECKSUM_PATH" || true)"
  if [[ -n "$EXPECTED_LINE" ]]; then
    EXPECTED_SUM="${EXPECTED_LINE%% *}"
    if command -v sha256sum >/dev/null 2>&1; then
      ACTUAL_SUM="$(sha256sum "$ASSET_PATH" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
      ACTUAL_SUM="$(shasum -a 256 "$ASSET_PATH" | awk '{print $1}')"
    else
      ACTUAL_SUM=""
      echo "No SHA-256 tool found; skipping checksum validation"
    fi

    if [[ -n "${ACTUAL_SUM:-}" && "$ACTUAL_SUM" != "$EXPECTED_SUM" ]]; then
      echo "Checksum mismatch for ${ASSET_NAME}" >&2
      exit 1
    fi
  else
    echo "SHA256SUMS did not include ${ASSET_NAME}; continuing without checksum verification"
  fi
else
  echo "SHA256SUMS not found for this release; continuing without checksum verification"
fi

mkdir -p "$EXTRACT_DIR"
tar -xzf "$ASSET_PATH" -C "$EXTRACT_DIR"

FOUND_BINARY=""
while IFS= read -r candidate; do
  if [[ "$(basename "$candidate")" == "$BINARY_NAME" ]]; then
    FOUND_BINARY="$candidate"
    break
  fi
done < <(find "$EXTRACT_DIR" -type f)

if [[ -z "$FOUND_BINARY" ]]; then
  FOUND_BINARY="$(find "$EXTRACT_DIR" -type f | head -n 1 || true)"
fi

if [[ -z "$FOUND_BINARY" ]]; then
  echo "No binary found in ${ASSET_NAME}" >&2
  exit 1
fi

install -m 0755 "$FOUND_BINARY" "$TARGET_PATH"

append_once() {
  local file="$1"
  local line="$2"

  mkdir -p "$(dirname "$file")"
  touch "$file"

  if ! grep -Fqx "$line" "$file"; then
    printf '\n%s\n' "$line" >>"$file"
    echo "Updated ${file}"
  fi
}

ensure_local_bin_on_path() {
  if [[ "$SKIP_PATH_UPDATE" == "true" || "$INSTALL_DIR" != "$HOME/.local/bin" ]]; then
    return
  fi

  case ":$PATH:" in
    *":$HOME/.local/bin:"*)
      return
      ;;
  esac

  SHELL_NAME="$(basename "${SHELL:-}")"
  case "$SHELL_NAME" in
    zsh)
      RC_FILE="$HOME/.zshrc"
      PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
      ;;
    bash)
      if [[ -f "$HOME/.bashrc" ]]; then
        RC_FILE="$HOME/.bashrc"
      else
        RC_FILE="$HOME/.bash_profile"
      fi
      PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
      ;;
    fish)
      RC_FILE="$HOME/.config/fish/config.fish"
      PATH_LINE='fish_add_path $HOME/.local/bin'
      ;;
    *)
      echo "Add $HOME/.local/bin to your PATH manually."
      return
      ;;
  esac

  append_once "$RC_FILE" "$PATH_LINE"
  echo "Reload your shell or source ${RC_FILE} to pick up the PATH change."
}

install_completions() {
  local shell_name completion_path

  if [[ "$SKIP_COMPLETIONS" == "true" ]]; then
    echo "Skipping shell completions"
    return
  fi

  shell_name="$(basename "${SHELL:-}")"
  case "$shell_name" in
    bash)
      completion_path="$HOME/.local/share/bash-completion/completions/${BINARY_NAME}"
      mkdir -p "$(dirname "$completion_path")"
      "$TARGET_PATH" completion bash >"$completion_path"
      echo "Installed bash completions to ${completion_path}"
      ;;
    zsh)
      completion_path="$HOME/.zsh/completions/_${BINARY_NAME}"
      mkdir -p "$(dirname "$completion_path")"
      "$TARGET_PATH" completion zsh >"$completion_path"
      echo "Installed zsh completions to ${completion_path}"
      append_once "$HOME/.zshrc" 'fpath=("$HOME/.zsh/completions" $fpath)'
      if ! grep -Fq "compinit" "$HOME/.zshrc"; then
        printf '\nautoload -Uz compinit\ncompinit\n' >>"$HOME/.zshrc"
        echo "Updated $HOME/.zshrc"
      fi
      ;;
    fish)
      completion_path="$HOME/.config/fish/completions/${BINARY_NAME}.fish"
      mkdir -p "$(dirname "$completion_path")"
      "$TARGET_PATH" completion fish >"$completion_path"
      echo "Installed fish completions to ${completion_path}"
      ;;
    *)
      echo "Skipping shell completions for unsupported shell: ${shell_name:-unknown}"
      ;;
  esac
}

ensure_local_bin_on_path
install_completions

if [[ "$SKIP_VERIFY" != "true" ]]; then
  echo "Verifying installation"
  "$TARGET_PATH" --version
fi

echo "Installed ${BINARY_NAME} to ${TARGET_PATH}"
