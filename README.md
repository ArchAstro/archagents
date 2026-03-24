# ArchAgent CLI

Public distribution repository for the ArchAgent CLI.

## Install

GitHub Releases are the canonical distribution path.

### macOS

Prefer Homebrew when available:

```bash
brew install ArchAstro/tools/archagent
```

Fallback to the installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
```

### Linux

Use the installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/ArchAstro/archagents/main/install.sh | bash
```

### Windows

Use the PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/ArchAstro/archagents/main/install.ps1 | iex
```

## Claude Code Plugins

Add the marketplace and install the public plugins:

```text
/plugin marketplace add archastro/archagents
/plugin install cli@archagents
/plugin install agents@archagents
```

The `helper` plugin remains in `ArchAstro/claude-plugins`.
