#!/bin/sh
set -e

# Пока миграции не закоммичены, создаём их при старте (через volume они попадут в репозиторий).
python manage.py makemigrations org accounts hr_requests notifications integrations academy --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
python manage.py seed
# Кадровые данные из 1С:ЗУП (заглушка mocks/zup). Недоступна — предупреждение, запуск продолжается.
python manage.py sync_zup --trigger startup || true

# ASGI (uvicorn): обычные запросы + долгие SSE-соединения уведомлений (/api/v1/notifications/stream)
if [ "$DJANGO_DEV_SERVER" = "1" ]; then
    # Режим разработки (docker-compose.dev.yml): перезапуск при изменении .py
    exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload --lifespan off
fi
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 3 --lifespan off --proxy-headers --forwarded-allow-ips "*"
