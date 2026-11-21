#!/usr/bin/env bash
# Usage: trace.sh <node-id>
# Run on entering every workflow node. Prints "[harness] node: <id>" and, when HARNESS_TRACE is set,
# appends "node <id>" to it, so a run's path is recorded.
set -euo pipefail
id="${1:?node id required}"
echo "[harness] node: $id"
[ -n "${HARNESS_TRACE:-}" ] && echo "node $id" >> "$HARNESS_TRACE"
exit 0
