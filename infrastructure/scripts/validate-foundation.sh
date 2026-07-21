#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repository_root"

fail() {
  printf 'foundation validation failed: %s\n' "$1" >&2
  exit 1
}

required_files='AGENTS.md
README.md
docs/requirements.md
docs/architecture.md
docs/IMPLEMENTATION_PLAN.md
.editorconfig
.gitignore
.env.example
Makefile
docker-compose.yml
.github/workflows/foundation.yml'

printf '%s\n' "$required_files" | while IFS= read -r path; do
  [ -f "$path" ] || fail "missing required file $path"
done

for directory in backend frontend infrastructure docs/adr docs/runbooks .github/workflows; do
  [ -d "$directory" ] || fail "missing required directory $directory"
done

for target in bootstrap up down logs migrate seed test lint openapi check; do
  grep -Eq "^${target}:" Makefile || fail "missing Make target $target"
done

for document in docs/requirements.md docs/architecture.md docs/IMPLEMENTATION_PLAN.md; do
  grep -Fq "($document)" README.md || fail "README does not link to $document"
done

if [ -e requirements.md ] || [ -e architecture.md ] || [ -e IMPLEMENTATION_PLAN.md ]; then
  fail 'source documents must remain under docs/'
fi

if grep -Ev '^[[:space:]]*(#|$)' .env.example \
  | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' \
  | grep -Ev '^FABRICASSIST_[A-Z0-9_]*=' >/dev/null; then
  fail 'every FabricAssist-owned variable in .env.example must use FABRICASSIST_'
fi

for expected in \
  FABRICASSIST_ENVIRONMENT \
  FABRICASSIST_DATABASE_URL \
  FABRICASSIST_VALKEY_URL \
  FABRICASSIST_S3_ENDPOINT_URL \
  FABRICASSIST_S3_ACCESS_KEY \
  FABRICASSIST_S3_SECRET_KEY \
  FABRICASSIST_S3_BUCKET \
  FABRICASSIST_S3_FORCE_PATH_STYLE \
  FABRICASSIST_LOG_LEVEL; do
  grep -Eq "^${expected}=" .env.example || fail "missing $expected placeholder"
done

for service in \
  fabricassist-api \
  fabricassist-worker \
  fabricassist-postgres \
  fabricassist-valkey \
  fabricassist-minio \
  fabricassist-minio-init; do
  grep -Eq "^  ${service}:" docker-compose.yml || fail "missing Compose service $service"
done

grep -Eq '^name: fabricassist$' docker-compose.yml \
  || fail 'Compose project name must be fabricassist'


for required_infrastructure_file in \
  infrastructure/compose/minio/initialize-bucket.sh \
  infrastructure/scripts/wait-for-service.sh \
  infrastructure/scripts/reset-local.sh \
  infrastructure/scripts/smoke.sh; do
  [ -x "$required_infrastructure_file" ] || fail "missing executable Phase 4 infrastructure file $required_infrastructure_file"
done

if grep -Eq '^[[:space:]]*container_name:' docker-compose.yml; then
  fail 'container_name must not be set'
fi

if grep -Eqi '^[[:space:]]*(redis|db|storage|api|worker):' docker-compose.yml; then
  fail 'shorthand or forbidden Compose service name found'
fi

if grep -Eqi 'image:[[:space:]]*(redis|mongo)|mongodb|mongo:' docker-compose.yml; then
  fail 'forbidden database or cache image found'
fi

legacy_pattern='cc''a:|Care''Lens|Clean''Lens|Clean''Assistant|Fabric'' Assistant'
if grep -R -n -E "$legacy_pattern" --exclude-dir=.git --exclude-dir=node_modules . >/dev/null; then
  fail 'legacy product name or cache prefix found'
fi

for required_backend_file in \
  backend/pyproject.toml \
  backend/uv.lock \
  backend/Dockerfile \
  backend/src/fabricassist/__init__.py \
  backend/src/fabricassist/settings.py \
  backend/src/fabricassist/api/main.py \
  backend/src/fabricassist/infrastructure/database.py; do
  [ -f "$required_backend_file" ] || fail "missing Phase 2 backend file $required_backend_file"
done

for later_phase_path in \
  backend/src/fabricassist/worker \
  backend/src/fabricassist/domain \
  backend/src/fabricassist/services \
  backend/src/fabricassist/repositories \
  'frontend/apps/client/src/app/(operator)' \
  'frontend/apps/client/src/app/(operator)'; do
  [ ! -e "$later_phase_path" ] || fail "later-phase implementation found: $later_phase_path"
done


for required_frontend_file in \
  frontend/package.json \
  frontend/pnpm-lock.yaml \
  frontend/pnpm-workspace.yaml \
  frontend/apps/client/package.json \
  frontend/apps/client/app.config.ts \
  frontend/apps/client/src/app/_layout.tsx \
  frontend/packages/api-client/src/generated/index.ts \
  frontend/packages/translations/src/index.ts; do
  [ -f "$required_frontend_file" ] || fail "missing Phase 3 frontend file $required_frontend_file"
done

grep -Fq '"name": "fabricassist-app"' frontend/apps/client/package.json \
  || fail 'frontend application package name must be fabricassist-app'
grep -Fq "slug: 'fabricassist'" frontend/apps/client/app.config.ts \
  || fail 'Expo slug must be fabricassist'

grep -Fq 'backend/src/fabricassist/' docs/adr/001-modular-monolith.md \
  || fail 'ADR does not document the canonical Python src layout'
grep -Fq 'fabricassist.api' docs/adr/001-modular-monolith.md \
  || fail 'ADR does not document the API package name'

if grep -R -n -E --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude=validate-foundation.sh \
  -- '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}' . >/dev/null; then
  fail 'probable real secret material found'
fi

docker compose config --quiet
printf '%s\n' 'FabricAssist repository foundation checks passed.'
