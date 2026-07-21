#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"

./infrastructure/scripts/wait-for-service.sh http://localhost:"${FABRICASSIST_API_PORT:-8000}"/api/v1/health/live 30
docker compose exec -T fabricassist-postgres pg_isready -U "${FABRICASSIST_POSTGRES_USER:-fabricassist_dev}" -d "${FABRICASSIST_POSTGRES_DB:-fabricassist_dev}"
docker compose exec -T fabricassist-valkey valkey-cli ping | grep -qx PONG
docker compose exec -T fabricassist-minio mc alias set fabricassist-local http://127.0.0.1:9000 "${FABRICASSIST_S3_ACCESS_KEY:-fabricassist-local}" "${FABRICASSIST_S3_SECRET_KEY:-change-me-local-minio}"
docker compose exec -T fabricassist-minio mc ls "fabricassist-local/${FABRICASSIST_S3_BUCKET:-fabricassist-local}" >/dev/null
docker compose exec -T fabricassist-minio mc anonymous get "fabricassist-local/${FABRICASSIST_S3_BUCKET:-fabricassist-local}" | grep -Eqi 'none|private'
printf '%s\n' 'FabricAssist local infrastructure smoke checks passed.'
