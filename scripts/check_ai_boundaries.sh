#!/usr/bin/env bash
set -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BOUNDARIES_FILE="$ROOT_DIR/.ai-boundaries.yml"
ARTIFACT_DIR="${AI_BOUNDARY_ARTIFACT_DIR:-${VERIFY_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/release}}"
COMPARE_REF="${AI_BOUNDARY_COMPARE_REF:-${VERIFY_COMPARE_REF:-}}"

mkdir -p "$ARTIFACT_DIR"

if [[ ! -f "$BOUNDARIES_FILE" ]]; then
  printf 'missing %s\n' "$BOUNDARIES_FILE" >&2
  exit 1
fi

section_items() {
  local section="$1"
  awk -v wanted="$section" '
    /^[a-z_]+:/ { current=$1; sub(":", "", current); next }
    current == wanted && /^[[:space:]]*-/ {
      sub(/^[[:space:]]*-[[:space:]]*/, "", $0)
      gsub(/"/, "", $0)
      print $0
    }
  ' "$BOUNDARIES_FILE"
}

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

matches_prefix() {
  local file="$1"
  local prefix="$2"
  [[ "$file" == "$prefix" || "$file" == "$prefix"* ]]
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

is_bootstrap_file() {
  case "$1" in
    .ai-boundaries.yml|.gitignore|Makefile|scripts/check_ai_boundaries.sh|scripts/check_spec_contract.sh|scripts/verify_release.sh|docs/specifications/_template/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

changed=()
while IFS= read -r item; do
  [[ -n "$item" ]] && changed+=("$item")
done < <(changed_files | sed '/^$/d' | sort -u)

forbidden=()
while IFS= read -r item; do
  [[ -n "$item" ]] && forbidden+=("$item")
done < <(section_items forbidden | sed '/^$/d')

approval_required=()
while IFS= read -r item; do
  [[ -n "$item" ]] && approval_required+=("$item")
done < <(section_items approval_required | sed '/^$/d')

forbidden_hits=()
approval_hits=()

for file in "${changed[@]}"; do
  for prefix in "${forbidden[@]}"; do
    if matches_prefix "$file" "$prefix"; then
      forbidden_hits+=("$file")
    fi
  done
  for prefix in "${approval_required[@]}"; do
    if matches_prefix "$file" "$prefix"; then
      approval_hits+=("$file")
    fi
  done
done

bootstrap=0
if ! git -C "$ROOT_DIR" cat-file -e "HEAD:.ai-boundaries.yml" >/dev/null 2>&1; then
  bootstrap=1
fi

bootstrap_approval_only=1
for file in "${approval_hits[@]}"; do
  if ! is_bootstrap_file "$file"; then
    bootstrap_approval_only=0
  fi
done

{
  printf '{\n'
  printf '  "changed_files": '
  json_array "${changed[@]}"
  printf ',\n'
  printf '  "approval_required": '
  json_array "${approval_hits[@]}"
  printf ',\n'
  printf '  "forbidden": '
  json_array "${forbidden_hits[@]}"
  printf ',\n'
  printf '  "bootstrap": %s,\n' "$bootstrap"
  printf '  "approved": %s\n' "${AI_BOUNDARY_APPROVED:-0}"
  printf '}\n'
} >"$ARTIFACT_DIR/ai_boundaries.json"

if (( ${#forbidden_hits[@]} > 0 )); then
  printf 'forbidden AI boundary paths changed:\n' >&2
  printf '  %s\n' "${forbidden_hits[@]}" >&2
  exit 1
fi

if (( ${#approval_hits[@]} > 0 )); then
  if [[ "${AI_BOUNDARY_APPROVED:-0}" == "1" ]]; then
    exit 0
  fi
  if (( bootstrap == 1 && bootstrap_approval_only == 1 )); then
    printf 'bootstrap approval-required harness files changed; recorded in ai_boundaries.json\n'
    exit 0
  fi
  printf 'approval-required paths changed; set AI_BOUNDARY_APPROVED=1 only after owner approval:\n' >&2
  printf '  %s\n' "${approval_hits[@]}" >&2
  exit 1
fi
