"""Live-уведомления: PostgreSQL LISTEN/NOTIFY → Server-Sent Events.

1. Создано уведомление (в любом процессе: backend, worker, команда) → NOTIFY в канал PostgreSQL.
   NOTIFY внутри транзакции доставляется только после коммита — откаченное уведомление не «вылетит».
2. Каждый процесс backend держит ОДНО соединение LISTEN (Hub) и раздаёт события
   открытым SSE-соединениям нужного пользователя через asyncio-очереди.
3. Поток GET /api/v1/notifications/stream отдаёт событие в браузер сразу; каждые 20 с — ping,
   чтобы прокси не закрыли соединение. Обрыв связи браузер переподключает сам (EventSource).
"""
import asyncio
import json
import logging
from collections import defaultdict

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

CHANNEL = "janamen_notifications"


def notify_created(notification) -> None:
    """post_save Notification → NOTIFY. Только PostgreSQL (на SQLite live-режима нет, работает опрос)."""
    if connection.vendor != "postgresql":
        return
    payload = json.dumps({"user_id": notification.user_id, "id": notification.id})
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_notify(%s, %s)", [CHANNEL, payload])


def _conninfo() -> str:
    import psycopg

    db = settings.DATABASES["default"]
    return psycopg.conninfo.make_conninfo(
        host=db["HOST"], port=db.get("PORT") or 5432, dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"]
    )


class Hub:
    """Одно LISTEN-соединение на процесс + очереди подписчиков по пользователям."""

    def __init__(self):
        self.subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)
        self._task: asyncio.Task | None = None

    async def subscribe(self, user_id: int) -> asyncio.Queue:
        self._ensure_listener()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue) -> None:
        self.subscribers[user_id].discard(queue)
        if not self.subscribers[user_id]:
            self.subscribers.pop(user_id, None)

    def dispatch(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except ValueError:
            return
        for queue in list(self.subscribers.get(data.get("user_id"), ())):
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:  # вкладка «зависла» — пропускаем, данные догрузит опрос
                pass

    def _ensure_listener(self) -> None:
        if connection.vendor != "postgresql":
            return
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._listen())

    async def _listen(self) -> None:
        import psycopg

        while True:
            try:
                conn = await psycopg.AsyncConnection.connect(_conninfo(), autocommit=True)
                async with conn:
                    await conn.execute(f"LISTEN {CHANNEL}")
                    async for notify in conn.notifies():
                        self.dispatch(notify.payload)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — база перезапускается: переподключиться
                logger.exception("SSE: LISTEN-соединение потеряно, переподключение через 3 с")
                await asyncio.sleep(3)


hub = Hub()
