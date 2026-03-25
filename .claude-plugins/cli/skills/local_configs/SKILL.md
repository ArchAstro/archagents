---
name: local_configs
description: Use when the user wants to set up or manage local config files for an ArchAstro project — initialize a configs directory, edit configs locally, sync from the server, or deploy local changes. Trigger phrases include "set up configs", "init configs", "configs directory", "sync configs", "deploy configs", "edit config locally", "local config management", "configs init".
allowed-tools: ["Bash(archagent:*)"]
---

# ArchAstro Local Config Management

Set up and manage a local `configs/` directory for editing agent configs as files, syncing with the server, and deploying changes.

This skill depends on the `cli` plugin for CLI installation and authentication. Use that plugin's commands instead of trying to install or authenticate the CLI manually inside this skill.

## What is Local Config Management?

Instead of creating and editing configs one-by-one through CLI CRUD commands, you can manage them as local files in a `configs/` directory. This enables:
- **Edit configs in your editor** with syntax highlighting and version control
- **Batch deploy** all changes in dependency order
- **Sync** server configs down to local files
- **Browser editor** for visual editing of individual configs

The CLI tracks the mapping between local files and server configs in a manifest file.

## Always Start with State

Every invocation must begin by understanding the current project state:

```
archagent auth status
ls configs/ 2>/dev/null || echo "No configs directory"
```

Determine:
- Does a `configs/` directory already exist?
- Is the user starting a new project or working with an existing one?
- Do they want to pull configs from the server or push local changes?

## Routing

### CLI not installed or too old

Before any config work, verify the CLI:

- Read `plugin-compatibility.json` from the plugin root.
- Prefer `plugins.cli.minimumCliVersion`, fall back to the top-level `minimumCliVersion`.
- Run `archagent --version`. If missing or older than the resolved minimum, direct the user to `/cli:install`.
- If authentication or app selection is missing, direct the user to `/cli:auth`.

### User wants to set up a configs directory for the first time

1. **Initialize the config directory**:
   ```
   archagent configs init
   ```
   This enables local config management and creates the configured `configs/` directory if needed. It does not automatically sync remote configs; use `archagent configs sync` next when you want local files.

2. **Explain the layout**: After init, the directory looks like:
   ```
   configs/
   ├── .archastro-manifest.json    # Maps local files to server configs (do not edit manually)
   ├── agents/                     # AgentTemplate configs
   ├── skills/                     # Skill bundles
   ├── scripts/                    # Script configs
   ├── workflows/                  # Workflow configs
   └── ...                         # Other config kinds
   ```

   Managed virtual paths also follow these prefixes on the server: `skills/`, `scripts/`, and `workflows/`.

3. **Offer next steps**: Ask if the user wants to create a new config (`archagent configs sample <Kind>`) or sync existing configs from the server.

### User wants to pull configs from the server

Sync server configs to local files:
```
archagent configs sync
```

This downloads all configs for the current app and writes them as local YAML files. The manifest tracks the file-to-config mapping.

### User wants to create a new config locally

1. **Get a sample** for the config kind:
   ```
   archagent configs kinds
   archagent configs sample <Kind> --to-file ./configs/<category>/<name>.yaml
   ```

   Common kinds: `AgentTemplate`, `Script`, `Workflow`, `Persona`

2. **Edit the file** — the user can edit in their editor or use the browser editor:
   ```
   archagent configs edit ./configs/<category>/<name>.yaml
   ```
   This opens the config in the ArchAstro browser editor with live validation.

3. **Or create a blank config in the browser**:
   ```
   archagent configs new
   archagent configs new --kind Script my-script.yaml
   ```

### User wants to validate local configs

Validate a specific config file:
```
archagent configs validate -k <Kind> -f ./configs/<category>/<name>.yaml
```

For scripts specifically, use the dedicated validator:
```
archagent validate script --file ./scripts/my-script.archscript
```

### User wants to deploy local changes

Push all local config changes to the server:
```
archagent configs deploy
```

This:
- Compares local files against the manifest
- Uploads new and changed configs in dependency order
- Updates the manifest with new server IDs

**Important**: `configs deploy` syncs config files only. It does not create agents. To provision an agent from a template, use `archagent deploy agent <file>` separately.

### User wants to move or rename a config file

If a local config file is moved or renamed:
```
archagent configs mv <old-path> <new-path>
```

This updates the manifest mapping without affecting the server config.

### User has manifest issues

If the manifest gets out of sync:
```
archagent configs manifest-repair
```

This re-normalizes the manifest and resolves any inconsistencies.

## Typical Workflows

### New project from scratch
```
archagent configs init
archagent configs sample AgentTemplate --to-file ./configs/agents/my-agent.yaml
# Edit the file...
archagent configs validate -k AgentTemplate -f ./configs/agents/my-agent.yaml
archagent configs deploy
archagent deploy agent ./configs/agents/my-agent.yaml
```

### Pull existing project and make changes
```
archagent configs init
archagent configs sync
# Edit files locally...
archagent configs deploy
```

### Quick edit via browser
```
archagent configs edit ./configs/scripts/my-script.yaml
# Opens in browser with live validation
# Changes are saved to the server and synced back to the local file
```

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not manually edit `.archastro-manifest.json` — use CLI commands.
- Do not ask the user to pick raw subcommands when intent is clear.
- Keep responses concise and operational.
- Always recommend `configs deploy` over individual `create config` calls when working with local files.
