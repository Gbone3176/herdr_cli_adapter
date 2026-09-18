# Herdr CLI Adapters

[简体中文](README.zh-CN.md) | English

Adapters that expose agent lifecycle state and task metadata from CLI coding agents in Herdr's sidebar.

This repository is intentionally provider-neutral. It contains no API keys, private URLs, machine paths, or account data.

## Sidebar demo

The adapters report each CLI's lifecycle state, model, and short task title to the Herdr sidebar:

![Herdr sidebar showing Codex and Kimi agent states](assets/herdr-sidebar-demo.png)

The example shows Codex and Kimi agents displayed together with `working`/`idle` state labels and task summaries.

## Current adapters

- `kimi`: Kimi Code lifecycle hooks with task-short-name and model metadata.
- `claude`: Claude Code hook wrapper.
- `codex`: Codex hook wrapper.
- `generic`: a small reporter usable by other CLIs that can invoke shell hooks.

### Codex Goal mode

The Codex adapter recognizes goal tool payloads and `/goal` prompts. It keeps the
Herdr state as `working` across intermediate `Stop` hooks while a goal is active,
then returns to `idle` when a goal reports a terminal status. The marker is scoped
to the Herdr pane and expires after 24 hours as a safety fallback.

## Events

Adapters translate CLI events into:

`session_start`, `working`, `blocked`, and `idle`.

Metadata uses Herdr's `pane.report_metadata` surface with `task` and `model` tokens. The protocol is documented in `protocol/event.schema.json`.

## Install Kimi adapter

```bash
./install.sh kimi
```

The installer copies the hook, merges the Kimi entries, and configures Herdr's
sidebar metadata rows. Re-running it is idempotent. Existing configuration and
installed scripts receive timestamped backups before they change.

Install the other adapters the same way, or install all three:

```bash
./install.sh codex
./install.sh claude
./install.sh all
```

The installer honors `CODEX_HOME`, `KIMI_CODE_HOME`,
`CLAUDE_SHARED_SETTINGS_FILE`, `HERDR_ADAPTER_HOME`, and `HERDR_CONFIG_PATH`,
so it works with managed or relocated configuration directories.

Codex uses the current HooksToml shape (`[[hooks.Event]]` plus
`[[hooks.Event.hooks]]` and `type = "command"`); the installer upgrades the
old repository fragment instead of appending an invalid legacy `[[hooks]]`
entry.

Kimi Code `0.14.0+` is required. Herdr must run with `HERDR_ENV=1`.

## Safety

Hooks fail closed when Herdr variables are unavailable. Socket failures do not interrupt the agent. See `SECURITY.md` before publishing additional adapters.

## Development

```bash
./tests/test_reporter.sh
./tests/test_installer.sh
```

The project is designed to work with POSIX shell and Python 3; it adds no
runtime dependency.
