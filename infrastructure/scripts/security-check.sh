#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"

./infrastructure/scripts/validate-foundation.sh

tracked_env_files=$(
  git ls-files |
    grep -E '(^|/)\.env($|[.-])' |
    grep -Ev '(^|/)\.env\.example$' |
    while IFS= read -r file; do
      if [ -f "$file" ]; then
        printf '%s\n' "$file"
      fi
    done
)
if [ -n "$tracked_env_files" ]; then
  printf '%s\n%s\n' 'Tracked environment file detected:' "$tracked_env_files" >&2
  exit 1
fi

if grep -R -n -E \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.terraform --exclude-dir=node_modules \
  --exclude-dir=android --exclude-dir=ios --exclude-dir=dist --exclude-dir=build \
  --exclude='.env' --exclude='.env-*' --exclude='.env.example' \
  --exclude='staging.tfvars.example' \
  -- \
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{32,}' \
  .; then
  printf '%s\n' 'Probable committed secret detected.' >&2
  exit 1
fi

grep -Fq 'USER fabricassist' backend/Dockerfile
if grep -Eq 'allow_origins=.*\*|CORS_ALLOWED_ORIGINS=\*' backend/src/fabricassist/api/main.py .env.example; then
  printf '%s\n' 'Wildcard CORS policy detected.' >&2
  exit 1
fi

cd backend
uv run pytest tests/unit/test_settings.py tests/unit/test_production_hardening.py
printf '%s\n' 'FabricAssist local security checks passed.'
