#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_FILE="$ROOT_DIR/harness/harness.lock"

read_lock() {
  python3 -I -B -S - "$LOCK_FILE" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if set(payload) != {"schema_version", "module", "version"} or payload["schema_version"] != 1:
    raise SystemExit("invalid harness/harness.lock")
module, version = payload["module"], payload["version"]
if module != "github.com/Fueav/harnessctl" or not isinstance(version, str) or not version.startswith("v"):
    raise SystemExit("invalid harnessctl module or version")
print(f"{module}\t{version}")
PY
}

IFS=$'\t' read -r MODULE VERSION < <(read_lock)
EXPECTED="harnessctl $VERSION"

if [[ -n "${HARNESSCTL_BIN:-}" ]]; then
  [[ -x "$HARNESSCTL_BIN" ]] || { printf 'HARNESSCTL_BIN is not executable\n' >&2; exit 2; }
  [[ "$($HARNESSCTL_BIN version)" == "$EXPECTED" ]] || {
    printf 'HARNESSCTL_BIN version does not match %s\n' "$VERSION" >&2
    exit 2
  }
  exec "$HARNESSCTL_BIN" "$@" --repo "$ROOT_DIR"
fi

if command -v harnessctl >/dev/null 2>&1 && [[ "$(harnessctl version)" == "$EXPECTED" ]]; then
  exec harnessctl "$@" --repo "$ROOT_DIR"
fi

INSTALL_DIR="${GOBIN:-$ROOT_DIR/.tools/bin}"
mkdir -p "$INSTALL_DIR"
GOBIN="$INSTALL_DIR" go install "$MODULE/cmd/harnessctl@$VERSION"
[[ "$($INSTALL_DIR/harnessctl version)" == "$EXPECTED" ]] || {
  printf 'installed harnessctl version does not match %s\n' "$VERSION" >&2
  exit 2
}
exec "$INSTALL_DIR/harnessctl" "$@" --repo "$ROOT_DIR"
