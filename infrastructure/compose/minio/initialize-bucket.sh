#!/bin/sh
set -eu

: "${FABRICASSIST_S3_ACCESS_KEY:?missing FABRICASSIST_S3_ACCESS_KEY}"
: "${FABRICASSIST_S3_SECRET_KEY:?missing FABRICASSIST_S3_SECRET_KEY}"
: "${FABRICASSIST_S3_BUCKET:?missing FABRICASSIST_S3_BUCKET}"

mc alias set fabricassist-local http://fabricassist-minio:9000 \
  "$FABRICASSIST_S3_ACCESS_KEY" "$FABRICASSIST_S3_SECRET_KEY"
mc mb --ignore-existing "fabricassist-local/$FABRICASSIST_S3_BUCKET"
mc anonymous set none "fabricassist-local/$FABRICASSIST_S3_BUCKET"
printf '%s\n' 'Initialized private local FabricAssist bucket.'
