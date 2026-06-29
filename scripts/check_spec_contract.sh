#!/usr/bin/env bash
set -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="${SPEC_CONTRACT_ARTIFACT_DIR:-${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}}"
COMPARE_REF="${SPEC_CONTRACT_COMPARE_REF:-${VERIFY_COMPARE_REF:-}}"

mkdir -p "$ARTIFACT_DIR"

changed_files() {
  if ! git -C "$ROOT_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
    git -C "$ROOT_DIR" ls-files --others --exclude-standard
    return 0
  fi

  if [[ -n "$COMPARE_REF" ]] && git -C "$ROOT_DIR" rev-parse --verify "$COMPARE_REF^{commit}" >/dev/null 2>&1; then
    git -C "$ROOT_DIR" diff --name-only "$COMPARE_REF"...HEAD
  else
    git -C "$ROOT_DIR" diff --name-only HEAD
    git -C "$ROOT_DIR" diff --name-only --cached
  fi
  git -C "$ROOT_DIR" ls-files --others --exclude-standard
}

json_array() {
  local first=1
  printf '['
  for value in "$@"; do
    [[ "$first" == 0 ]] && printf ', '
    first=0
    printf '"%s"' "$(printf '%s' "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  done
  printf ']'
}

requires_spec_change=0
spec_changed=0
missing_spec_ids=()
required_files=()
spec_files=()

changed=()
while IFS= read -r item; do
  [[ -n "$item" ]] && changed+=("$item")
done < <(changed_files | sed '/^$/d' | sort -u)

for file in "${changed[@]}"; do
  case "$file" in
    docs/specifications/_template/*)
      ;;
    docs/specifications/*)
      spec_changed=1
      spec_files+=("$file")
      if [[ -f "$ROOT_DIR/$file" ]] && ! grep -Eq 'SPEC-[A-Z0-9_-]+' "$ROOT_DIR/$file"; then
        missing_spec_ids+=("$file")
      fi
      ;;
    docs/implementation-plans/*)
      spec_changed=1
      spec_files+=("$file")
      ;;
    app/api/*|app/runtime/*|app/bus/*|app/tasks/*|app/db/*|app/core/models.py|app/core/schemas.py|app/core/events.py|requirements.txt|docker-compose.yml|scripts/*|Makefile)
      requires_spec_change=1
      required_files+=("$file")
      ;;
  esac
done

status="passed"
reason=""

if (( ${#missing_spec_ids[@]} > 0 )); then
  status="failed"
  reason="missing spec ids"
elif (( requires_spec_change == 1 && spec_changed == 0 )); then
  if [[ "${SPEC_CONTRACT_APPROVED:-0}" == "1" ]]; then
    status="exempted"
    reason="SPEC_CONTRACT_APPROVED=1"
  else
    status="failed"
    reason="missing specification or implementation plan change"
  fi
fi

{
  printf '{\n'
  printf '  "status": "%s",\n' "$status"
  printf '  "reason": "%s",\n' "$reason"
  printf '  "requires_spec_change": %s,\n' "$requires_spec_change"
  printf '  "spec_changed": %s,\n' "$spec_changed"
  printf '  "required_files": '
  json_array "${required_files[@]}"
  printf ',\n'
  printf '  "spec_files": '
  json_array "${spec_files[@]}"
  printf ',\n'
  printf '  "missing_spec_ids": '
  json_array "${missing_spec_ids[@]}"
  printf '\n}\n'
} >"$ARTIFACT_DIR/spec_contract.json"

if [[ "$status" == "failed" ]]; then
  printf 'spec contract failed: %s\n' "$reason" >&2
  if (( ${#missing_spec_ids[@]} > 0 )); then
    printf 'spec files missing SPEC-* IDs:\n' >&2
    printf '  %s\n' "${missing_spec_ids[@]}" >&2
  fi
  if (( ${#required_files[@]} > 0 && spec_changed == 0 )); then
    printf 'changed files require a matching specification or implementation plan:\n' >&2
    printf '  %s\n' "${required_files[@]}" >&2
  fi
  exit 1
fi
