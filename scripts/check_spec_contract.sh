#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="${HARNESS_ARTIFACT_DIR:-${SPEC_CONTRACT_ARTIFACT_DIR:-${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}}}"
COMPARE_REF="${SPEC_CONTRACT_COMPARE_REF:-${VERIFY_COMPARE_REF:-${HARNESS_COMPARE_SHA:-}}}"
SNAPSHOT_FILE="${HARNESS_SNAPSHOT_FILE:-}"

mkdir -p "$ARTIFACT_DIR"

changed_files() {
  if [[ -n "$SNAPSHOT_FILE" && -f "$SNAPSHOT_FILE" ]]; then
    python3 -I -B -S - "$SNAPSHOT_FILE" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for change in payload.get("changes", []):
    path = change.get("path")
    if isinstance(path, str):
        print(path)
PY
    return
  fi
  if ! git -C "$ROOT_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
    git -C "$ROOT_DIR" ls-files --others --exclude-standard
    return
  fi
  if [[ -n "$COMPARE_REF" ]] && git -C "$ROOT_DIR" rev-parse --verify "$COMPARE_REF^{commit}" >/dev/null 2>&1; then
    git -C "$ROOT_DIR" diff --name-only "$COMPARE_REF"...HEAD
  fi
  git -C "$ROOT_DIR" diff --name-only HEAD
  git -C "$ROOT_DIR" diff --name-only --cached
  git -C "$ROOT_DIR" ls-files --others --exclude-standard
}

json_array() {
  local first=1 value
  printf '['
  for value in "$@"; do
    [[ "$first" == 0 ]] && printf ', '
    first=0
    printf '"%s"' "$(printf '%s' "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  done
  printf ']'
}

legacy_contract_errors=()
validate_legacy_contracts() {
  local file binding_count binding
  while IFS= read -r -d '' file; do
    binding_count="$(grep -Ec '^[[:space:]]*(-[[:space:]]*)?Workflow Class:' "$file" || true)"
    if [[ "$binding_count" != 1 ]]; then
      legacy_contract_errors+=("${file#"$ROOT_DIR/"}: expected exactly one Workflow Class binding")
      continue
    fi
    binding="$(grep -E '^[[:space:]]*(-[[:space:]]*)?Workflow Class:' "$file")"
    if ! grep -Eq 'HARNESS-(FOCUSED-CHANGE|SPEC-FIRST-FEATURE|VERIFICATION-INCIDENT|MAINTENANCE)' <<<"$binding"; then
      legacy_contract_errors+=("${file#"$ROOT_DIR/"}: unknown Workflow Class")
    fi
    if [[ "$file" == "$ROOT_DIR/docs/specifications/"* ]] && ! grep -Eq 'SPEC-[A-Z0-9][A-Z0-9_-]*' "$file"; then
      legacy_contract_errors+=("${file#"$ROOT_DIR/"}: missing SPEC-* ID")
    fi
  done < <(find "$ROOT_DIR/docs/specifications" "$ROOT_DIR/docs/implementation-plans" \
    -maxdepth 1 -type f -name '*.md' -print0)
}

validate_legacy_contracts

changed=()
while IFS= read -r item; do
  [[ -n "$item" ]] && changed+=("$item")
done < <(changed_files | sed '/^$/d' | sort -u)

requires_spec_change=0
spec_changed=0
required_files=()
spec_files=()

for file in ${changed[@]+"${changed[@]}"}; do
  case "$file" in
    docs/specifications/_template/*|specs/_template/*|specs/index.json)
      ;;
    docs/specifications/*|docs/implementation-plans/*|specs/*/spec.md)
      spec_changed=1
      spec_files+=("$file")
      ;;
    scripts/check_ai_boundaries.sh|scripts/check_project_release.sh|scripts/check_spec_contract.sh|scripts/check_spec_registry.sh|scripts/harnessctl.sh|scripts/verify_candidate.sh|scripts/verify_change.sh|scripts/verify_release.sh)
      ;;
    app/*|dockerhost/*|requirements.txt|docker-compose.yml|scripts/*|Makefile)
      requires_spec_change=1
      required_files+=("$file")
      ;;
  esac
done

status="passed"
reason=""
if (( ${#legacy_contract_errors[@]} > 0 )); then
  status="failed"
  reason="invalid legacy specification contract"
elif (( requires_spec_change == 1 && spec_changed == 0 )); then
  if [[ "${SPEC_CONTRACT_APPROVED:-0}" == 1 ]]; then
    status="passed"
    reason="explicit exemption: SPEC_CONTRACT_APPROVED=1"
  else
    status="failed"
    reason="missing specification change"
  fi
fi

{
  printf '{\n'
  printf '  "status": "%s",\n' "$status"
  printf '  "reason": "%s",\n' "$reason"
  printf '  "requires_spec_change": %s,\n' "$requires_spec_change"
  printf '  "spec_changed": %s,\n' "$spec_changed"
  printf '  "required_files": '
  if (( ${#required_files[@]} > 0 )); then
    json_array "${required_files[@]}"
  else
    printf '[]'
  fi
  printf ',\n  "spec_files": '
  if (( ${#spec_files[@]} > 0 )); then
    json_array "${spec_files[@]}"
  else
    printf '[]'
  fi
  printf ',\n  "legacy_contract_errors": '
  if (( ${#legacy_contract_errors[@]} > 0 )); then
    json_array "${legacy_contract_errors[@]}"
  else
    printf '[]'
  fi
  printf '\n}\n'
} >"$ARTIFACT_DIR/spec_contract.json"

if [[ "$status" == failed ]]; then
  printf 'spec contract failed: %s\n' "$reason" >&2
  if (( ${#legacy_contract_errors[@]} > 0 )); then
    printf '  %s\n' "${legacy_contract_errors[@]}" >&2
  fi
  if (( requires_spec_change == 1 && spec_changed == 0 )); then
    printf 'changed files require a matching specification change:\n' >&2
    printf '  %s\n' "${required_files[@]}" >&2
  fi
  exit 1
fi

printf 'spec contract %s: %s legacy specs, %s legacy plans\n' \
  "$status" \
  "$(find "$ROOT_DIR/docs/specifications" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')" \
  "$(find "$ROOT_DIR/docs/implementation-plans" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')"
