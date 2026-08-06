#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"

case "${FABRICASSIST_ENVIRONMENT:-development}" in
  development|test) ;;
  *) printf '%s\n' 'Refusing a restore drill outside development/test.' >&2; exit 1 ;;
esac

database=${FABRICASSIST_POSTGRES_DB:-fabricassist_dev}
user=${FABRICASSIST_POSTGRES_USER:-fabricassist_dev}
drill_database=fabricassist_restore_drill
backup=$(mktemp "${TMPDIR:-/tmp}/fabricassist-backup.XXXXXX")
trap 'rm -f "$backup"; docker compose exec -T fabricassist-postgres dropdb --if-exists -U "$user" "$drill_database" >/dev/null 2>&1 || true' EXIT

docker compose exec -T fabricassist-postgres pg_isready -U "$user" -d "$database" >/dev/null
source_head=$(docker compose exec -T fabricassist-postgres psql -U "$user" -d "$database" -Atc 'SELECT version_num FROM alembic_version')
test -n "$source_head"
docker compose exec -T fabricassist-postgres pg_dump -U "$user" -d "$database" -Fc >"$backup"
test -s "$backup"
docker compose exec -T fabricassist-postgres dropdb --if-exists -U "$user" "$drill_database"
docker compose exec -T fabricassist-postgres createdb -U "$user" "$drill_database"
docker compose exec -T fabricassist-postgres pg_restore -U "$user" -d "$drill_database" --exit-on-error <"$backup"

head=$(docker compose exec -T fabricassist-postgres psql -U "$user" -d "$drill_database" -Atc 'SELECT version_num FROM alembic_version')
test "$head" = "$source_head"
tables=$(docker compose exec -T fabricassist-postgres psql -U "$user" -d "$drill_database" -Atc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")
test "$tables" -gt 0
printf 'Backup/restore drill passed at Alembic head %s with %s public tables.\n' "$head" "$tables"
