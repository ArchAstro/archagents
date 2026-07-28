#!/usr/bin/env bash
#
# Canonical end-to-end proof for Vercel Sandbox-compatible installation.
#
# A real Linux container serves a fixture release over HTTP, removes /dev/fd
# to reproduce the sandbox boundary, and runs install.sh as a user would.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FIXTURE_DIR="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

"$ROOT_DIR/scripts/create-unix-fixtures.sh" \
  --output-dir "$FIXTURE_DIR" \
  --version 0.3.1 \
  --platform linux \
  --arch-label x64-musl

docker run --rm \
  --platform linux/amd64 \
  --volume "$ROOT_DIR:/workspace:ro" \
  --volume "$FIXTURE_DIR:/release:ro" \
  alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce \
  /bin/sh -eu -c '
    apk add --no-cache bash coreutils curl python3 >/dev/null

    # Reproduce Vercel Sandbox before crossing the installer boundary.
    rm -f /dev/fd
    test ! -e /dev/fd

    # Serve the release exactly as the installer expects to fetch it.
    cd /release
    python3 -m http.server 8123 --bind 127.0.0.1 >/tmp/fixtures.log 2>&1 &
    server_pid=$!
    trap "kill $server_pid" EXIT
    for attempt in $(seq 1 20); do
      if curl -fsS http://127.0.0.1:8123/SHA256SUMS >/dev/null; then
        break
      fi
      if [ "$attempt" -eq 20 ]; then
        cat /tmp/fixtures.log
        exit 1
      fi
      sleep 1
    done

    # Run the real installer and assert its externally observable result.
    mkdir -p /tmp/home
    HOME=/tmp/home \
      SHELL=/bin/bash \
      ARCHAGENT_RELEASE_BASE_URL=http://127.0.0.1:8123 \
      ARCHAGENT_VERSION=0.3.1 \
      ARCHAGENT_INSTALL_DIR=/tmp/home/.local/bin \
      ARCHAGENT_INSTALL_SKIP_PATH_UPDATE=true \
      ARCHAGENT_INSTALL_SKIP_COMPLETIONS=true \
      /workspace/install.sh

    test "$(/tmp/home/.local/bin/archagent --version)" = "0.3.1"
  '
