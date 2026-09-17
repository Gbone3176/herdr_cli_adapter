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

The installer copies the hook and prints the Kimi configuration entries to add. It never copies credentials and never overwrites an existing config without a backup.

Kimi Code `0.14.0+` is required. Herdr must run with `HERDR_ENV=1`.

## Safety

Hooks fail closed when Herdr variables are unavailable. Socket failures do not interrupt the agent. See `SECURITY.md` before publishing additional adapters.

## Development

```bash
./tests/test_reporter.sh
```

The project is designed to work with POSIX shell and Python 3; it adds no runtime dependency.
