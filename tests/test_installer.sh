#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/herdr-installer-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT

codex_home=$test_root/codex
kimi_home=$test_root/kimi
claude_home=$test_root/claude
adapter_home=$test_root/adapters
herdr_config=$test_root/herdr/config.toml
mkdir -p "$codex_home" "$kimi_home" "$claude_home"

cat >"$codex_home/config.toml" <<'EOF'
model = "test-model"

[[hooks]]
event = "SessionStart"
command = "bash ~/.herdr/adapters/codex/herdr-agent-state.sh session"
EOF
cat >"$claude_home/settings.json" <<'EOF'
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"bash \"$HOME/.herdr/adapters/claude/herdr-agent-state.sh\" session"}]}],"PreToolUse":[{"hooks":[{"type":"command","command":"echo keep-me"}]}]}}
EOF

HOME="$test_root/home" \
CODEX_HOME="$codex_home" \
KIMI_CODE_HOME="$kimi_home" \
CLAUDE_SHARED_SETTINGS_FILE="$claude_home/settings.json" \
HERDR_ADAPTER_HOME="$adapter_home" \
HERDR_CONFIG_PATH="$herdr_config" \
  "$repo/install.sh" all >/dev/null

python3 - "$codex_home/config.toml" "$kimi_home/config.toml" "$claude_home/settings.json" "$herdr_config" <<'PY'
import json
import sys
import tomllib
from pathlib import Path

codex_path, kimi_path, claude_path, herdr_path = map(Path, sys.argv[1:])
with codex_path.open("rb") as stream:
    codex = tomllib.load(stream)
assert codex["hooks"]["SessionStart"][0]["hooks"][0]["type"] == "command"
assert codex["hooks"]["Stop"][0]["hooks"][0]["type"] == "command"
assert "[[hooks]]" not in codex_path.read_text()
assert codex_path.read_text().count("herdr-agent-state.sh session") == 1

with kimi_path.open("rb") as stream:
    kimi = tomllib.load(stream)
assert len(kimi["hooks"]) == 6

claude = json.loads(claude_path.read_text())
assert "echo keep-me" in claude_path.read_text()
assert claude["hooks"]["SessionStart"][0]["hooks"][0]["type"] == "command"
assert claude_path.read_text().count("herdr-agent-state.sh session") == 1
assert str(Path(sys.argv[3]).parents[1] / "adapters" / "adapters" / "claude" / "herdr-agent-state.sh") in claude_path.read_text()

with herdr_path.open("rb") as stream:
    herdr = tomllib.load(stream)
assert herdr["ui"]["sidebar"]["agents"]["rows"][-1] == ["$task", "$model"]
print("configuration merge: ok")
PY

before=$(sha256sum "$codex_home/config.toml" "$kimi_home/config.toml" "$claude_home/settings.json" "$herdr_config")
HOME="$test_root/home" \
CODEX_HOME="$codex_home" \
KIMI_CODE_HOME="$kimi_home" \
CLAUDE_SHARED_SETTINGS_FILE="$claude_home/settings.json" \
HERDR_ADAPTER_HOME="$adapter_home" \
HERDR_CONFIG_PATH="$herdr_config" \
  "$repo/install.sh" all >/dev/null
after=$(sha256sum "$codex_home/config.toml" "$kimi_home/config.toml" "$claude_home/settings.json" "$herdr_config")
[ "$before" = "$after" ]

printf '%s\n' 'installer idempotence: ok'
