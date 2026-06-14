#!/bin/sh
set -e

# The persistent volume is mounted as root by Fly; reclaim it for the app
# user before dropping privileges.
chown -R app:app /app/data

export HOME=/app
exec setpriv --reuid=app --regid=app --init-groups "$@"
