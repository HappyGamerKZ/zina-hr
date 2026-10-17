"""Внутренняя шина доменных событий.

Модули не вызывают друг друга напрямую: hr_requests публикует событие,
notifications (а позже integrations) на него подписываются в AppConfig.ready().
"""
from collections import defaultdict
from typing import Callable

REQUEST_SUBMITTED = "request_submitted"
REQUEST_STATUS_CHANGED = "request_status_changed"
COURSE_ASSIGNED = "course_assigned"
COURSE_COMPLETED = "course_completed"

_handlers: dict[str, list[Callable]] = defaultdict(list)


def subscribe(event: str, handler: Callable) -> None:
    if handler not in _handlers[event]:
        _handlers[event].append(handler)


def publish(event: str, **payload) -> None:
    for handler in _handlers[event]:
        handler(**payload)
