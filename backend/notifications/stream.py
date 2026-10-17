"""GET /api/v1/notifications/stream — поток уведомлений (Server-Sent Events).

Обычный Django async-view, а не DRF: соединение долгое и асинхронное.
Пользователь — только из сессии; каждый получает только свои уведомления.

События:
    event: ready         data: {"unread": 3}                      — сразу после подключения
    event: notification  data: {<уведомление как в GET /notifications>, "unread": 4}
    : ping                                                       — каждые 20 с, чтобы соединение не закрылось
"""
import asyncio
import json

from asgiref.sync import sync_to_async
from django.http import JsonResponse, StreamingHttpResponse

from notifications.live import hub
from notifications.models import Notification
from notifications.serializers import NotificationSerializer

HEARTBEAT_SECONDS = 20


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@sync_to_async
def _unread(user_id: int) -> int:
    return Notification.objects.filter(user_id=user_id, is_read=False).count()


@sync_to_async
def _notification(notification_id: int, user_id: int) -> dict | None:
    n = Notification.objects.filter(pk=notification_id, user_id=user_id).first()
    return NotificationSerializer(n).data if n else None


async def notification_stream(request):
    user = await request.auser()
    if not user.is_authenticated:
        return JsonResponse({"detail": "Учётные данные не были предоставлены."}, status=403)
    queue = await hub.subscribe(user.id)

    async def events():
        try:
            yield "retry: 5000\n\n"  # через сколько браузеру переподключаться после обрыва
            yield sse("ready", {"unread": await _unread(user.id)})
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                data = await _notification(item["id"], user.id)
                if data:
                    yield sse("notification", {**data, "unread": await _unread(user.id)})
        finally:
            hub.unsubscribe(user.id, queue)

    response = StreamingHttpResponse(events(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # nginx: не копить события в буфере
    return response
