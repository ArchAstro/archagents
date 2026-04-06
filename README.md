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

## Codex Plugins

To install the Codex plugins:

```text
git clone https://github.com/ArchAstro/archagents.git
cd /path/to/archagents
codex
/plugins
```

Then open the `ArchAstro` marketplace and install `cli` and `agents`. If the marketplace does not appear, restart Codex from the repository root and open `/plugins` again.

The marketplace definition lives in [`.agents/plugins/marketplace.json`](./.agents/plugins/marketplace.json), and the plugin manifests live under [`plugins/`](./plugins). For repo-local discovery, the marketplace must point at plugin directories using repo-root-relative `./plugins/...` paths.

Codex skill entrypoints are harness-specific wrappers. Shared skill workflow detail lives in [`shared/skills/`](./shared/skills), while shared Claude command workflow detail lives in [`shared/commands/`](./shared/commands). This keeps Claude commands and Codex skills distinct while still avoiding duplicated operational markdown.
