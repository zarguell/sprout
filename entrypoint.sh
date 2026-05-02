#!/bin/sh
set -e

# Ensure data directories exist before starting
# (Volume mounts overlay image-created dirs, so we must create at runtime)
mkdir -p /app/data/db /app/data/photos

exec "$@"
