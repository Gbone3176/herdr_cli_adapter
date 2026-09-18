#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
home_dir=${HOME:-}
adapter_home=${HERDR_ADAPTER_HOME:-$home_dir/.herdr}
codex_home=${CODEX_HOME:-$home_dir/.codex}
kimi_home=${KIMI_CODE_HOME:-$home_dir/.kimi-code}
claude_config_dir=${CLAUDE_SHARED_CONFIG_DIR:-${CLAUDE_CONFIG_DIR:-$home_dir/.claude}}
claude_settings=${CLAUDE_SHARED_SETTINGS_FILE:-${CLAUDE_SETTINGS_FILE:-$claude_config_dir/settings.json}}
herdr_config=${HERDR_CONFIG_PATH:-${XDG_CONFIG_HOME:-$home_dir/.config}/herdr/config.toml}

usage() {
  cat >&2 <<EOF
Usage: $0 [--help] [kimi|claude|codex|generic|all]

The installer copies adapter files and merges hooks into the detected CLI
configuration. Existing files are backed up before they change.

Environment overrides:
  HERDR_ADAPTER_HOME       Adapter files (default: ~/.herdr)
  CODEX_HOME               Codex config directory (default: ~/.codex)
  KIMI_CODE_HOME           Kimi config directory (default: ~/.kimi-code)
  CLAUDE_SHARED_SETTINGS_FILE
  CLAUDE_SETTINGS_FILE     Claude settings JSON path
  HERDR_CONFIG_PATH        Herdr config TOML path
EOF
}

backup_if_present() {
  original=$1
  if [ ! -e "$original" ]; then
    return
  fi
  stamp=$(date -u +%Y%m%d%H%M%S)
  backup="$original.bak.$stamp"
  suffix=0
  while [ -e "$backup" ]; do
    suffix=$((suffix + 1))
    backup="$original.bak.$stamp.$suffix"
  done
  cp -p "$original" "$backup"
  echo "Backed up $original to $backup"
}

install_file() {
  source_file=$1
  target_file=$2
  file_mode=$3
  mkdir -p "$(dirname -- "$target_file")"
  if [ -e "$target_file" ] && ! cmp -s "$source_file" "$target_file"; then
    backup_if_present "$target_file"
  fi
  cp "$source_file" "$target_file"
  chmod "$file_mode" "$target_file"
}

configure() {
  kind=$1
  config_path=$2
  script_path=$3
  python3 "$repo_dir/tools/configure.py" "$kind" \
    --config "$config_path" \
    --script "$script_path" \
    --herdr-config "$herdr_config"
}

install_kimi() {
  hook_target="$kimi_home/hooks/herdr-agent-state.sh"
  install_file "$repo_dir/adapters/kimi/herdr-agent-state.sh" "$hook_target" 700
  install_file "$repo_dir/adapters/python/herdr_report.py" "$kimi_home/python/herdr_report.py" 700
  configure kimi "$kimi_home/config.toml" "$hook_target"
  echo "Installed Kimi adapter at $hook_target"
}

install_claude() {
  hook_target="$adapter_home/adapters/claude/herdr-agent-state.sh"
  install_file "$repo_dir/adapters/generic/herdr-report.sh" "$adapter_home/adapters/generic/herdr-report.sh" 700
  install_file "$repo_dir/adapters/python/herdr_report.py" "$adapter_home/adapters/python/herdr_report.py" 700
  install_file "$repo_dir/adapters/claude/herdr-agent-state.sh" "$hook_target" 700
  configure claude "$claude_settings" "$hook_target"
  echo "Installed Claude adapter at $hook_target"
}

install_codex() {
  hook_target="$adapter_home/adapters/codex/herdr-agent-state.sh"
  install_file "$repo_dir/adapters/generic/herdr-report.sh" "$adapter_home/adapters/generic/herdr-report.sh" 700
  install_file "$repo_dir/adapters/python/herdr_report.py" "$adapter_home/adapters/python/herdr_report.py" 700
  install_file "$repo_dir/adapters/codex/herdr-agent-state.sh" "$hook_target" 700
  configure codex "$codex_home/config.toml" "$hook_target"
  echo "Installed Codex adapter at $hook_target"
}

case "${1:-kimi}" in
  --help|-h)
    usage >&1
    ;;
  kimi)
    install_kimi
    ;;
  claude)
    install_claude
    ;;
  codex)
    install_codex
    ;;
  all)
    install_kimi
    install_claude
    install_codex
    ;;
  generic)
    echo "Use $repo_dir/adapters/generic/herdr-report.sh from your CLI hook configuration."
    ;;
  *)
    usage
    exit 2
    ;;
esac
