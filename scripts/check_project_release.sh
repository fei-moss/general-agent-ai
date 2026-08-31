#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" != --managed-test-resources ]]; then
  exec "$ROOT_DIR/scripts/with_test_resources.sh" --mode fresh -- python3 "$ROOT_DIR/scripts/test_resource_env.py" "$0" --managed-test-resources "$@"
fi
[[ "${HARNESS_RESOURCE_MODE:-}" == fresh && -n "${HARNESS_RESOURCE_RUN_ID:-}" ]] || { printf 'fresh managed test resources are required\n' >&2; exit 1; }
shift
ARTIFACT_DIR="${HARNESS_ARTIFACT_DIR:-${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}}"
PYTHON_BIN="${PYTHON:-${PY:-$ROOT_DIR/.venv/bin/python}}"
SUMMARY="$ARTIFACT_DIR/project_release_summary.json"

mkdir -p "$ARTIFACT_DIR"
cd "$ROOT_DIR" || exit 1

checks=()
statuses=()

run_check() {
  local name="$1"
  shift
  printf '==> %s\n' "$name"
  if "$@"; then
    printf 'PASS %s\n' "$name"
    checks+=("$name")
    statuses+=("passed")
    return 0
  fi
  printf 'FAIL %s\n' "$name" >&2
  checks+=("$name")
  statuses+=("failed")
  return 1
}

skip_check() {
  printf 'SKIP %s (%s)\n' "$1" "$2"
  checks+=("$1")
  statuses+=("skipped")
}

overall_status=0
run_check dockerhost_production_config "$PYTHON_BIN" scripts/check_dockerhost_production_config.py || overall_status=1
run_check production_deployment_contract "$PYTHON_BIN" scripts/check_production_deployment_contract.py || overall_status=1
run_check observability_assets "$PYTHON_BIN" scripts/validate_observability_assets.py || overall_status=1
run_check python_available "$PYTHON_BIN" --version || overall_status=1
run_check import_smoke "$PYTHON_BIN" -c 'import app.api.main; import app.runtime.orchestrator; import app.bus.event_bus; import app.core.events' || overall_status=1
run_check chat_behavior_eval "$PYTHON_BIN" -m pytest tests/test_chat_behavior_eval.py tests/test_chat_eval_closure.py -q || overall_status=1
run_check chat_eval_scorecard "$PYTHON_BIN" -m tests.chat_eval.scorecard --output "$ARTIFACT_DIR/chat_eval_scorecard.json" --strict || overall_status=1
run_check pytest "$PYTHON_BIN" -m pytest -q || overall_status=1

if command -v gitleaks >/dev/null 2>&1; then
  run_check gitleaks gitleaks detect --source "$ROOT_DIR" --no-git --redact || overall_status=1
else
  skip_check gitleaks "gitleaks is not installed; install it to enable local secret scanning"
fi

{
  printf '{\n'
  if (( overall_status == 0 )); then
    printf '  "status": "passed",\n'
  else
    printf '  "status": "failed",\n'
  fi
  printf '  "checks": [\n'
  for index in "${!checks[@]}"; do
    [[ "$index" != 0 ]] && printf ',\n'
    printf '    {"name": "%s", "status": "%s"}' "${checks[$index]}" "${statuses[$index]}"
  done
  printf '\n  ]\n}\n'
} >"$SUMMARY"

exit "$overall_status"
