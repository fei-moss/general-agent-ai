#!/usr/bin/env bash
set -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}"
LOG_DIR="$ARTIFACT_DIR/logs"
PYTHON_BIN="${PYTHON:-${PY:-python3}}"

mkdir -p "$LOG_DIR"

checks=()
statuses=()
required=()

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

append_check() {
  checks+=("$1")
  statuses+=("$2")
  required+=("$3")
}

run_check() {
  local name="$1"
  shift
  local log="$LOG_DIR/$name.log"
  printf '==> %s\n' "$name"
  if "$@" >"$log" 2>&1; then
    printf 'PASS %s\n' "$name"
    append_check "$name" "passed" "true"
    return 0
  fi
  printf 'FAIL %s (see %s)\n' "$name" "$log" >&2
  tail -n 80 "$log" >&2 || true
  append_check "$name" "failed" "true"
  return 1
}

skip_check() {
  local name="$1"
  local reason="$2"
  local log="$LOG_DIR/$name.log"
  printf 'SKIP %s (%s)\n' "$name" "$reason"
  printf '%s\n' "$reason" >"$log"
  append_check "$name" "skipped" "false"
}

write_summary() {
  local overall="passed"
  for idx in "${!checks[@]}"; do
    if [[ "${required[$idx]}" == "true" && "${statuses[$idx]}" != "passed" ]]; then
      overall="failed"
    fi
  done

  {
    printf '{\n'
    printf '  "overall": "%s",\n' "$overall"
    printf '  "artifact_dir": "%s",\n' "$(json_escape "$ARTIFACT_DIR")"
    printf '  "checks": [\n'
    for idx in "${!checks[@]}"; do
      [[ "$idx" != 0 ]] && printf ',\n'
      printf '    {"name": "%s", "status": "%s", "required": %s}' \
        "$(json_escape "${checks[$idx]}")" \
        "$(json_escape "${statuses[$idx]}")" \
        "${required[$idx]}"
    done
    printf '\n  ]\n'
    printf '}\n'
  } >"$ARTIFACT_DIR/summary.json"
}

cd "$ROOT_DIR" || exit 1

overall_status=0

run_check ai_boundaries "$ROOT_DIR/scripts/check_ai_boundaries.sh" || overall_status=1
run_check spec_contract "$ROOT_DIR/scripts/check_spec_contract.sh" || overall_status=1
run_check harness_workflows "$ROOT_DIR/scripts/check_harness_workflows.sh" || overall_status=1
run_check harness_workflow_tests "$ROOT_DIR/scripts/check_harness_workflows_test.sh" || overall_status=1
run_check dockerhost_production_config "$PYTHON_BIN" "$ROOT_DIR/scripts/check_dockerhost_production_config.py" || overall_status=1
run_check observability_assets "$PYTHON_BIN" "$ROOT_DIR/scripts/validate_observability_assets.py" || overall_status=1
run_check python_available "$PYTHON_BIN" --version || overall_status=1
run_check import_smoke "$PYTHON_BIN" -c 'import app.api.main; import app.runtime.orchestrator; import app.bus.event_bus; import app.core.events' || overall_status=1
run_check pytest "$PYTHON_BIN" -m pytest -q || overall_status=1

if command -v gitleaks >/dev/null 2>&1; then
  run_check gitleaks gitleaks detect --source "$ROOT_DIR" --no-git --redact || overall_status=1
else
  skip_check gitleaks "gitleaks is not installed; install it to enable local secret scanning"
fi

write_summary

if (( overall_status != 0 )); then
  printf 'release verification failed; evidence written to %s\n' "$ARTIFACT_DIR" >&2
  exit "$overall_status"
fi

printf 'release verification evidence written to %s\n' "$ARTIFACT_DIR"
