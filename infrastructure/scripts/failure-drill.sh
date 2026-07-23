#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
case "${FABRICASSIST_ENVIRONMENT:-development}" in development|test) ;; *) exit 1 ;; esac

case "${1:-}" in
  valkey)
    before=$(docker compose exec -T fabricassist-postgres psql -U "${FABRICASSIST_POSTGRES_USER:-fabricassist_dev}" -d "${FABRICASSIST_POSTGRES_DB:-fabricassist_dev}" -Atc 'SELECT count(*) FROM scans')
    docker compose stop fabricassist-valkey
    curl --fail --silent http://localhost:${FABRICASSIST_API_PORT:-8000}/api/v1/health/live >/dev/null
    after=$(docker compose exec -T fabricassist-postgres psql -U "${FABRICASSIST_POSTGRES_USER:-fabricassist_dev}" -d "${FABRICASSIST_POSTGRES_DB:-fabricassist_dev}" -Atc 'SELECT count(*) FROM scans')
    test "$before" = "$after"
    docker compose start fabricassist-valkey
    ;;
  worker)
    docker compose kill -s KILL fabricassist-worker
    docker compose up -d --wait fabricassist-worker
    docker compose ps fabricassist-worker
    ;;
  *)
    printf '%s\n' 'usage: failure-drill.sh valkey|worker' >&2
    exit 64
    ;;
esac
printf 'Failure drill %s passed.\n' "$1"
