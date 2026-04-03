---
name: manage-configs
description: Use when the user wants to set up or manage local config files for an ArchAstro project — initialize a configs directory, edit configs locally, sync from the server, or deploy local changes. Trigger phrases include "set up configs", "init configs", "configs directory", "sync configs", "deploy configs", "edit config locally", "local config management".
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
   archagent init --enable-configs
   ```
   This enables local config management and creates the configured `configs/` directory if needed. It does not automatically sync remote configs; use `archagent sync configs` next when you want local files.

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

3. **Offer next steps**: Ask if the user wants to create a new config (`archagent describe configsample <Kind>`) or sync existing configs from the server.

### User wants to pull configs from the server

Sync server configs to local files:
```
archagent sync configs
```

This downloads all configs for the current app — including skills, scripts, and workflows — and writes them as local files in the correct directories. The manifest tracks the file-to-config mapping.

After syncing, the directory structure reflects server state:
```
configs/
├── agents/                     # AgentTemplate configs (.yaml)
├── skills/my-skill/            # Skill bundles (SKILL.md + supporting files)
├── scripts/                    # Script configs (.agentscript)
├── workflows/                  # Workflow configs (.json)
└── ...                         # Other config kinds
```

You can then edit any file locally and run `archagent deploy configs` to push changes back.

### User wants to create a new config locally

For **scripts**, **skills**, and **workflows**, prefer the dedicated commands or create files directly in the correct directory:

- **Script**: Write a `.agentscript` file in `configs/scripts/`:
  ```
  configs/scripts/my-script.agentscript
  ```
- **Skill**: Create a `SKILL.md` (with frontmatter) in `configs/skills/<slug>/`:
  ```
  configs/skills/my-skill/SKILL.md
  configs/skills/my-skill/prompts/greeting.liquid   # optional supporting files
  ```
- **Workflow**: Write a `.json` file in `configs/workflows/`:
  ```
  configs/workflows/my-workflow.json
  ```

For **other config kinds** (AgentTemplate, Persona, etc.), get a sample:
```
archagent list configkinds
archagent describe configsample <Kind> --to-file ./configs/<category>/<name>.yaml
```

You can also use the browser editor:
```
archagent edit config ./configs/<category>/<name>.yaml
```

### User wants to validate local configs

Validate a specific config file:
```
archagent validate config -k <Kind> -f ./configs/<category>/<name>.yaml
```

For scripts specifically, use the dedicated validator:
```
archagent validate script --file ./configs/scripts/my-script.agentscript
```

### User wants to deploy local changes

Push all local config changes to the server:
```
archagent deploy configs
```

This:
- Compares local files against the manifest
- Uploads new and changed configs in dependency order
- Updates the manifest with new server IDs

#### Managed directory conventions

`deploy configs` enforces conventions for three managed directories:

| Directory | Convention |
|-----------|-----------|
| `skills/<slug>/` | All files become `File` kind. `SKILL.md` is the root — name and description are extracted from its YAML frontmatter. Other files (`.liquid`, `.yaml`, `.js`, etc.) become supporting skill files. |
| `scripts/` | Only `.agentscript` files and `.yaml`/`.json` with `kind: Script` are allowed. Other file types are rejected. |
| `workflows/` | Only `.json` files and `.yaml` with a `Workflow*` kind are allowed. Other file types are rejected. |

Files outside these directories use standard kind inference from file extension or YAML content.

**Important**: `deploy configs` syncs config files only. It does not create agents. To provision an agent from a template, use `archagent deploy agent <file>` separately.

### User wants to move or rename a config file

If a local config file is moved or renamed:
```
archagent update configpath <old-path> <new-path>
```

This updates the manifest mapping without affecting the server config.

### User has manifest issues

If the manifest gets out of sync:
```
archagent validate configmanifest
```

This re-normalizes the manifest and resolves any inconsistencies.

## Typical Workflows

### New project from scratch
```
archagent init --enable-configs
archagent describe configsample AgentTemplate --to-file ./configs/agents/my-agent.yaml
# Edit the file...
archagent validate config -k AgentTemplate -f ./configs/agents/my-agent.yaml
archagent deploy configs
archagent deploy agent ./configs/agents/my-agent.yaml
```

### Create a skill via local files
```
archagent init --enable-configs
mkdir -p configs/skills/my-skill
# Write SKILL.md with frontmatter (name, description)
# Add supporting files (prompts, references, etc.)
archagent deploy configs
# Skill is now visible via: archagent list skills
```

### Create a script via local files
```
archagent init --enable-configs
# Write script source directly
echo 'println("hello")' > configs/scripts/my-script.agentscript
archagent deploy configs
# Script is now visible via: archagent describe script my-script
```

### Pull existing project and make changes
```
archagent init --enable-configs
archagent sync configs
# Edit files locally...
archagent deploy configs
```

### Quick edit via browser
```
archagent edit config ./configs/agents/my-agent.yaml
# Opens in browser with live validation
# Changes are saved to the server and synced back to the local file
```

## Response Rules

- Do not inspect or edit credential files directly — use the CLI only.
- Do not manually edit `.archastro-manifest.json` — use CLI commands.
- Do not ask the user to pick raw subcommands when intent is clear.
- Keep responses concise and operational.
- Always recommend `deploy configs` over individual `create config` calls when working with local files.
