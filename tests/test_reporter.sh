#!/bin/sh
set -eu
script=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/adapters/generic/herdr-report.sh
HERDR_ENV=0 "$script" idle </dev/null
printf '%s\n' 'reporter smoke test passed'
