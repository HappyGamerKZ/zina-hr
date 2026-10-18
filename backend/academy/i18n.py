"""Язык содержимого курсов: казахский текст, если интерфейс на казахском и перевод заполнен, иначе русский.

Язык запроса определяет LocaleMiddleware по заголовку Accept-Language (фронтенд шлёт выбранный RU/KZ).
"""
from django.utils.translation import get_language


def is_kk() -> bool:
    return (get_language() or "").startswith("kk")


def tr(obj, field: str) -> str:
    """Поле на языке запроса: obj.<field>_kk для казахского (если заполнено), иначе obj.<field>."""
    if is_kk():
        value = getattr(obj, f"{field}_kk", "")
        if value:
            return value
    return getattr(obj, field)
