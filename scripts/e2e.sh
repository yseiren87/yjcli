#!/usr/bin/env bash
# Run the yjcli end-to-end scenarios into ./sandbox (git-ignored).
#   scripts/e2e.sh            all cases
#   scripts/e2e.sh -k wizard  cases whose name contains "wizard"
#   scripts/e2e.sh -v         print yjcli output for failed cases
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python scripts/e2e.py "$@"
