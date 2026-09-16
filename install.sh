#!/bin/sh
set -eu

adapter="${1:-kimi}"
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$adapter" in
  kimi)
    target="${KIMI_CODE_HOME:-$HOME/.kimi-code}/hooks/herdr-agent-state.sh"
    mkdir -p "$(dirname -- "$target")" "$(dirname -- "$target")/../python"
    if [ -e "$target" ]; then cp "$target" "$target.bak"; fi
    cp "$root/adapters/kimi/herdr-agent-state.sh" "$target"
    cp "$root/adapters/python/herdr_report.py" "$(dirname -- "$target")/../python/herdr_report.py"
    chmod 700 "$target"
    echo "Installed Kimi hook at $target"
    echo "Add the documented hook entries from adapters/kimi/config.toml to Kimi config."
    ;;
  generic)
    echo "Use adapters/generic/herdr-report.sh from your CLI hook configuration."
    ;;
  claude|codex)
    target="${HERDR_ADAPTER_HOME:-$HOME/.herdr}/adapters/$adapter"
    mkdir -p "$target" "$(dirname -- "$target")/generic" "$(dirname -- "$target")/python"
    cp "$root/adapters/generic/herdr-report.sh" "$(dirname -- "$target")/generic/herdr-report.sh"
    cp "$root/adapters/python/herdr_report.py" "$(dirname -- "$target")/python/herdr_report.py"
    chmod 700 "$(dirname -- "$target")/generic/herdr-report.sh"
    chmod 700 "$(dirname -- "$target")/python/herdr_report.py"
    cp "$root/adapters/$adapter/herdr-agent-state.sh" "$target/herdr-agent-state.sh"
    chmod 700 "$target/herdr-agent-state.sh"
    echo "Installed $adapter adapter at $target"
    echo "Merge the configuration from adapters/$adapter/ into your CLI config."
    ;;
  *) echo "Usage: $0 [kimi|generic]" >&2; exit 2;;
esac
