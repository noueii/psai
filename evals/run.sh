#!/usr/bin/env bash
# Run the AI evals headless in Claude Code, on throwaway copies, with psai and the scenario's stacks loaded as
# plugins for the run only (--plugin-dir). Never installs anything into the real HOME. Costs money: keep it small.
# Usage: evals/run.sh [--runs N] [--model M] [--budget USD] [--keep] [--stack <stack repo>] [scenario.yaml ...]
# With no scenarios: psai's own (evals/scenarios/psai/); with --stack, that stack's evals/scenarios/ with it loaded.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v claude >/dev/null || { echo "claude isn't installed" >&2; exit 1; }
args=(); scen=()
while [ $# -gt 0 ]; do
  case "$1" in
    --runs|--model|--budget|--stack) args+=("$1" "$2"); shift ;;
    --keep) args+=("$1") ;;
    *) scen+=("$1") ;;
  esac
  shift
done
shopt -s nullglob
[ ${#scen[@]} -gt 0 ] || [[ " ${args[*]-} " == *" --stack "* ]] || scen=(evals/scenarios/psai/*.yaml)
exec python3 evals/driver.py ${args[@]+"${args[@]}"} ${scen[@]+"${scen[@]}"}
