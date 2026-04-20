---
targets:
  claude-command: install.md
  codex-skill: install
skill:
  name: install
  description: Use when the user wants to install, upgrade, or bootstrap the ArchAgent CLI. Trigger phrases include "install archagent", "install the archagent CLI", "set up archagent", "upgrade archagent", "archagent not found", "archagent command not found", "install the CLI", "get archagent running".
  allowed-tools: ["Bash(archagent:*)", "Bash(brew:*)", "Bash(curl:*)", "Bash(bash:*)", "Bash(sh:*)", "Bash(pwsh:*)", "Bash(powershell:*)"]
command:
  description: Install the ArchAgent platform CLI
  allowed-tools: ["Bash(archagent:*)", "Bash(brew:*)", "Bash(curl:*)", "Bash(bash:*)", "Bash(sh:*)", "Bash(pwsh:*)", "Bash(powershell:*)"]
---

# Install ArchAgent CLI

Install or upgrade the public `archagent` binary from Homebrew or GitHub Releases.

## Workflow

1. **Check whether the CLI is already installed**:
   ```
   archagent --version
   ```
   If this succeeds, record the version.

2. **If the CLI is present** and the user didn't ask to upgrade, confirm the version and stop.

3. **If the CLI is missing or the user asked to upgrade**, install it using the public distribution path:
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

5. **On failure, help troubleshoot the public install path**:
   - Missing `brew` is expected on Linux and some macOS setups; fall back to `install.sh`.
   - `Permission denied` usually means they need `--install-dir` or a user-writable target directory.
   - `command not found: archagent` after install usually means the install directory is not on `PATH`.
   - Release download failures usually mean the target release asset has not been published yet.

6. **On success**, tell the user the CLI is ready and {{#CLAUDE_COMMAND}}suggest `/archagents:auth`{{/CLAUDE_COMMAND}}{{#SKILL}}suggest they run `archagent auth login` to authenticate{{/SKILL}}.
