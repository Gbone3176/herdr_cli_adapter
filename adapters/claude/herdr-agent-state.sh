#!/bin/sh
set -eu
export HERDR_AGENT_LABEL=claude
exec "$(CDPATH= cd -- "$(dirname -- "$0")/../generic" && pwd)/herdr-report.sh" "$@"
