#!/bin/sh
set -eu

if [ "${1:-}" != '--confirm' ]; then
  printf '%s\n' 'Refusing reset. Re-run as: make reset-local CONFIRM=1' >&2
  exit 64
fi

case "${FABRICASSIST_ENVIRONMENT:-development}" in
  development|test) ;;
  *) printf '%s\n' 'Refusing reset outside development or test.' >&2; exit 1;;
esac

printf '%s\n' 'Removing only FabricAssist Compose volumes:'
docker compose config --volumes | sed 's/^/ - /'
docker compose down --volumes --remove-orphans
