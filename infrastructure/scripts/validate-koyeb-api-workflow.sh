#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repository_root"

workflow=.github/workflows/deploy-alpha.yml

[ -f "$workflow" ] || {
  printf '%s\n' "Koyeb workflow is missing: $workflow" >&2
  exit 1
}

ruby -e 'require "yaml"; YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true)' "$workflow"

require_line() {
  grep -Fq -- "$1" "$workflow" || {
    printf '%s\n' "Koyeb workflow is missing: $1" >&2
    exit 1
  }
}

for required in \
  'uses: koyeb-community/koyeb-actions@v2' \
  'uses: koyeb/action-git-deploy@v1' \
  'service-instance-type: free' \
  'service-regions: fra' \
  'git-builder: docker' \
  'git-sha: ${{ needs.quality.outputs.git_sha }}' \
  'git-workdir: backend' \
  'git-docker-dockerfile: Dockerfile' \
  'service-checks: "8000:http:/api/v1/health/live"' \
  'FABRICASSIST_ACCESS_TOKEN_SECRET=@FABRICASSIST_ACCESS_TOKEN_SECRET' \
  'FABRICASSIST_DATABASE_URL=@FABRICASSIST_DATABASE_URL' \
  'FABRICASSIST_DATABASE_MIGRATION_URL=@FABRICASSIST_DATABASE_MIGRATION_URL' \
  'FABRICASSIST_S3_ACCESS_KEY=@FABRICASSIST_S3_ACCESS_KEY' \
  'FABRICASSIST_S3_SECRET_KEY=@FABRICASSIST_S3_SECRET_KEY' \
  'FABRICASSIST_QSTASH_TOKEN=@FABRICASSIST_QSTASH_TOKEN' \
  'FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY=@FABRICASSIST_QSTASH_CURRENT_SIGNING_KEY' \
  'FABRICASSIST_QSTASH_NEXT_SIGNING_KEY=@FABRICASSIST_QSTASH_NEXT_SIGNING_KEY'; do
  require_line "$required"
done

grep -Fq -- 'PORT:-8000' backend/Dockerfile \
  && grep -Fq -- '--workers 1' backend/Dockerfile || {
  printf '%s\n' 'API Dockerfile must honor PORT and start one uvicorn worker.' >&2
  exit 1
}

if grep -Eqi '(^|[^[:alnum:]_])(celery|alembic)([[:space:]]|$)' backend/Dockerfile; then
  printf '%s\n' 'API Dockerfile must not start Celery or Alembic.' >&2
  exit 1
fi

printf '%s\n' 'Koyeb API workflow and container contract checks passed.'
