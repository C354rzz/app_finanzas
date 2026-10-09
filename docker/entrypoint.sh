#!/bin/sh
set -e
if [ "${DJANGO_MIGRAR:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi
exec "$@"
