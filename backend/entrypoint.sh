#!/bin/sh
set -e

# Пока миграции не закоммичены, создаём их при старте (через volume они попадут в репозиторий).
python manage.py makemigrations org accounts hr_requests notifications integrations academy --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
python manage.py seed

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -
