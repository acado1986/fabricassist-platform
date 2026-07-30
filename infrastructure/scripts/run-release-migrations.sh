#!/usr/bin/env bash
# Apply Alembic migrations with bounded retries for managed PostgreSQL restarts.
set -u -o pipefail

readonly max_attempts=4
readonly retry_delay_seconds="${FABRICASSIST_MIGRATION_RETRY_DELAY_SECONDS:-5}"
case "$retry_delay_seconds" in
  *[!0-9]*|'')
    printf '%s\n' 'FABRICASSIST_MIGRATION_RETRY_DELAY_SECONDS must be a non-negative integer.' >&2
    exit 64
    ;;
esac
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

is_transient_database_shutdown() {
  grep --ignore-case --quiet --extended-regexp \
    'AdminShutdown|terminating connection due to administrator command|server closed the connection unexpectedly|connection.*(reset|refused|timed out)|could not connect to server|SSL connection has been closed unexpectedly' \
    "$output_file"
}

for attempt in $(seq 1 "$max_attempts"); do
  if uv run --project backend alembic -c backend/alembic.ini upgrade head 2>&1 | tee "$output_file"; then
    exit 0
  fi

  status=${PIPESTATUS[0]}
  if ! is_transient_database_shutdown; then
    printf '%s\n' 'Migration failed with a non-transient error; not retrying.' >&2
    exit "$status"
  fi
  if [ "$attempt" -eq "$max_attempts" ]; then
    printf 'Migration database connection did not recover after %s attempts.\n' "$max_attempts" >&2
    exit "$status"
  fi

  delay=$((attempt * retry_delay_seconds))
  printf 'Transient database shutdown detected; retrying migration in %s seconds (%s/%s).\n' \
    "$delay" "$attempt" "$max_attempts" >&2
  sleep "$delay"
done
