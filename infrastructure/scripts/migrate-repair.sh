#!/usr/bin/env bash
set -euo pipefail

revision="${1:-}"
if [[ -z "$revision" || ! "$revision" =~ ^[A-Za-z0-9_]+$ ]]; then
  printf 'Usage: %s <known-good-revision>\n' "$0" >&2
  exit 2
fi

printf 'WARNING: stamping the local database to Alembic revision %s, then upgrading to head.\n' "$revision" >&2
printf 'This is recovery for schema drift; do not use it as the normal migration path.\n' >&2

docker compose exec -T fabricassist-api alembic -c /app/alembic.ini history >/dev/null
docker compose exec -T fabricassist-api alembic -c /app/alembic.ini stamp "$revision"
docker compose exec -T fabricassist-api alembic -c /app/alembic.ini upgrade head

docker compose exec -T fabricassist-postgres sh -ceu '
  test "$(psql -Atqc "select version_num from alembic_version")" = "20260731_0020"
  for table in ai_runs ai_run_images ai_run_events; do
    psql -v ON_ERROR_STOP=1 -Atqc "select 1 from information_schema.tables where table_schema = '\''public'\'' and table_name = '\''$table'\''" | grep -qx 1
  done
'
printf 'Migration repair and schema verification passed.\n'
