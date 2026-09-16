#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../python" && pwd)
exec python3 "$root/herdr_report.py" "$@"
