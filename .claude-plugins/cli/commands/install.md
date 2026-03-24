---
description: Install the ArchAgent platform CLI
allowed-tools: ["Bash(archagent:*)", "Bash(brew:*)", "Bash(curl:*)", "Bash(bash:*)", "Bash(sh:*)", "Bash(pwsh:*)", "Bash(powershell:*)"]
---

# Install ArchAgent CLI

Install or upgrade the public `archagent` binary from Homebrew or GitHub Releases.

## Instructions

1. **Check whether the CLI is already installed**:
   ```
   archagent --version
   ```
   If this succeeds, record the version. The minimum supported version for the plugins in this repo is `0.3.1`.

2. **If the CLI is present and at least `0.3.1`**, confirm the version and stop unless the user explicitly asked to upgrade.

3. **If the CLI is missing or older than `0.3.1`**, install it using the public distribution path:
   - On macOS, if Homebrew is available:
     ```
     brew install ArchAstro/tools/archagent
     ```
     If the formula is already installed, run:
     ```
     brew upgrade ArchAstro/tools/archagent
     ```
   - On Linux or macOS without Homebrew:
     ```
     curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
     ```
   - On Windows PowerShell:
     ```powershell
     irm https://raw.githubusercontent.com/ArchAstro/archagents/main/install.ps1 | iex
     ```

4. **Verify installation**:
   ```
   archagent --version
   ```
   Confirm that the version is now `0.3.1` or newer.

5. **On success**, tell the user the CLI is ready and suggest `/cli:auth`.

6. **On failure**, help troubleshoot the public install path:
   - missing `brew` is expected on Linux and some macOS setups; fall back to `install.sh`
   - `Permission denied` usually means they need `--install-dir` or a user-writable target directory
   - `command not found: archagent` after install usually means the install directory is not on `PATH`
   - release download failures usually mean the target release asset has not been published yet
