#!/usr/bin/env bash
set -euo pipefail

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
runner="$repository_root/infrastructure/scripts/run-alpha-migrations.sh"
temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT

cat > "$temporary_directory/uv" <<'EOF'
#!/usr/bin/env bash
set -eu
attempt_file="${FAKE_UV_ATTEMPT_FILE:?}"
mode="${FAKE_UV_MODE:?}"
attempt=$(($(cat "$attempt_file") + 1))
printf '%s' "$attempt" > "$attempt_file"
case "$mode" in
  transient_then_success)
    if [ "$attempt" -lt 3 ]; then
      printf '%s\n' 'psycopg.errors.AdminShutdown: terminating connection due to administrator command' >&2
      exit 1
    fi
    ;;
  deterministic_failure)
    printf '%s\n' 'alembic.util.exc.CommandError: invalid migration revision' >&2
    exit 7
    ;;
  *)
    printf 'unknown fake uv mode: %s\n' "$mode" >&2
    exit 64
    ;;
esac
EOF
chmod +x "$temporary_directory/uv"

run_case() {
  local mode=$1 expected_status=$2 expected_attempts=$3
  local attempt_file="$temporary_directory/$mode-attempts"
  printf '0' > "$attempt_file"
  set +e
  PATH="$temporary_directory:$PATH" \
    FAKE_UV_MODE="$mode" \
    FAKE_UV_ATTEMPT_FILE="$attempt_file" \
    FABRICASSIST_MIGRATION_RETRY_DELAY_SECONDS=0 \
    "$runner"
  local status=$?
  set -e
  [ "$status" -eq "$expected_status" ] || {
    printf 'expected %s to exit %s, got %s\n' "$mode" "$expected_status" "$status" >&2
    exit 1
  }
  [ "$(cat "$attempt_file")" -eq "$expected_attempts" ] || {
    printf 'expected %s to run %s times\n' "$mode" "$expected_attempts" >&2
    exit 1
  }
}

run_case transient_then_success 0 3
run_case deterministic_failure 7 1
printf '%s\n' 'Alpha migration retry runner checks passed.'
