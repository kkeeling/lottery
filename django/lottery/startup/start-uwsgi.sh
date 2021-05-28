#!/bin/bash

echo "Waiting for Postgres..."
python ./startup/wait-for-postgres.py

python manage.py migrate --noinput
python manage.py collectstatic --noinput
uwsgi --ini /opt/lottery/uwsgi.ini --http :8000