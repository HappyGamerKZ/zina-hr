FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_STATIC_ROOT=/static

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["sh", "./entrypoint.sh"]
