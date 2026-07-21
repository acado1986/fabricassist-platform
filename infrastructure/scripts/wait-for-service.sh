#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  printf '%s\n' 'usage: wait-for-service.sh <url> <timeout-seconds>' >&2
  exit 64
fi

url=$1
timeout=$2
case "$timeout" in *[!0-9]*|'') printf '%s\n' 'timeout must be a positive integer' >&2; exit 64;; esac

deadline=$(( $(date +%s) + timeout ))
until curl --fail --silent --show-error "$url" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    printf 'timed out waiting for %s\n' "$url" >&2
    exit 1
  fi
  sleep 1
done
