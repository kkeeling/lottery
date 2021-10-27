#!/bin/bash

echo "Waiting for Postgres..."
python ./startup/wait-for-postgres.py
echo "Migrating database..."
python manage.py migrate --noinput
echo "Starting runserver..."
python manage.py runserver 0.0.0.0:8000