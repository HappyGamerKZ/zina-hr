"""Закрытое хранилище резюме.

PDF кандидатов — персональные данные, поэтому они НЕ лежат в /media (её nginx отдаёт любому по ссылке).
Файлы хранятся в отдельном томе (PRIVATE_MEDIA_ROOT, в docker compose — /private) без публичного URL
и отдаются только через GET /api/v1/recruitment/candidates/{id}/resume после проверки прав.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage() -> FileSystemStorage:
    # функция, а не объект: путь читается из настроек при обращении (тесты подменяют его на временную папку)
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)
