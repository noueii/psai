#!/usr/bin/env bash
# Run the AI evals (L3, L4) headless, on throwaway copies. Never touches the real HOME's harness files.
# Usage: evals/run.sh [--tool claude|omp|all] [--runs N] [--model M] [--budget USD] [--keep] [scenario.yaml ...]
# With no scenarios, runs every file in evals/scenarios/. Summaries go to evals/results/.
set -euo pipefail
cd "$(dirname "$0")/.."
tools=(claude); args=(); scen=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tool) shift; [ "$1" = all ] && tools=(claude omp) || tools=("$1") ;;
    --runs|--model|--budget) args+=("$1" "$2"); shift ;;
    --keep) args+=("$1") ;;
    *) scen+=("$1") ;;
  esac
  shift
done
[ ${#scen[@]} -gt 0 ] || scen=(evals/scenarios/*.yaml)
rc=0
for t in "${tools[@]}"; do
  if ! command -v "$t" >/dev/null; then echo "skip $t: not installed"; continue; fi
  python3 evals/driver.py --tool "$t" "${args[@]}" "${scen[@]}" || rc=1
done
exit $rc
