#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repository_root"

workflow=.github/workflows/deploy-alpha.yml

[ -f "$workflow" ] || {
  printf '%s\n' "Render workflow is missing: $workflow" >&2
  exit 1
}

ruby -e 'require "yaml"; YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true)' "$workflow"

require_line() {
  grep -Fq -- "$1" "$workflow" || {
    printf '%s\n' "Render workflow is missing: $1" >&2
    exit 1
  }
}

for required in \
  'RENDER_DEPLOY_HOOK_URL' \
  'SELECTED_SHA: ${{ needs.quality.outputs.git_sha }}' \
  'curl --fail --silent --show-error --get' \
  '--data-urlencode "ref=${SELECTED_SHA}"' \
  'FABRICASSIST_ALPHA_API_URL' \
  '/api/v1/health/live' \
  '/api/v1/health/ready'; do
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

printf '%s\n' 'Render API workflow and container contract checks passed.'
