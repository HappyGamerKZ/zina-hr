#!/bin/sh
set -e

# Пока миграции не закоммичены, создаём их при старте (через volume они попадут в репозиторий).
python manage.py makemigrations org accounts hr_requests notifications integrations academy --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
python manage.py seed
# Кадровые данные из 1С:ЗУП (заглушка mocks/zup). Недоступна — предупреждение, запуск продолжается.
python manage.py sync_zup --trigger startup || true

if [ "$DJANGO_DEV_SERVER" = "1" ]; then
    # Режим разработки (docker-compose.dev.yml): перезапуск при изменении кода
    exec python manage.py runserver 0.0.0.0:8000
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -
