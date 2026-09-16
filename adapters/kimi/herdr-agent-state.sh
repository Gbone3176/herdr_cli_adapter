#!/bin/sh
set -eu
export HERDR_AGENT_LABEL=kimi
export HERDR_AGENT_MODEL="${HERDR_AGENT_MODEL:-kimi-k3}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../python" && pwd)
exec python3 "$root/herdr_report.py" "$@"
