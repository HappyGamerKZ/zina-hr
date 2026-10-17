"""Live-уведомления (SSE): NOTIFY при создании, раздача по пользователям, поток событий.

docker compose exec backend python manage.py test notifications
"""
import asyncio
import json
from unittest import mock

from asgiref.sync import sync_to_async
from django.db import connection
from django.test import AsyncClient, TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from notifications import live
from notifications.live import Hub, hub
from notifications.models import Notification

STREAM = "/api/v1/notifications/stream"


class LiveNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")

    def create(self, user, title="Тест"):
        return Notification.objects.create(user=user, type="request_status_changed", title=title, link="/")

    def test_created_notification_sends_pg_notify(self):
        with mock.patch.object(live, "notify_created") as notify:
            n = self.create(self.alice)
            n.title = "изменено"
            n.save()  # повторное сохранение — не новое уведомление
        notify.assert_called_once_with(n)

        with CaptureQueriesContext(connection) as ctx:
            self.create(self.alice)
        self.assertTrue(any("pg_notify" in q["sql"] for q in ctx.captured_queries))

    def test_hub_routes_only_to_recipient(self):
        async def scenario():
            h = Hub()
            with mock.patch.object(h, "_ensure_listener"):
                qa = await h.subscribe(self.alice.id)
                qb = await h.subscribe(self.bob.id)
            h.dispatch(json.dumps({"user_id": self.alice.id, "id": 1}))
            h.dispatch("не json")  # мусор не роняет раздачу
            h.unsubscribe(self.bob.id, qb)
            return qa.get_nowait(), qb.empty(), dict(h.subscribers)

        item, bob_empty, subscribers = asyncio.run(scenario())
        self.assertEqual(item["id"], 1)
        self.assertTrue(bob_empty)
        self.assertNotIn(self.bob.id, subscribers)

    async def test_stream_requires_login(self):
        res = await AsyncClient().get(STREAM)
        self.assertEqual(res.status_code, 403)

    async def test_stream_sends_ready_and_own_notifications(self):
        client = AsyncClient()
        await client.aforce_login(self.alice)
        await sync_to_async(self.create)(self.alice, "старое непрочитанное")
        with mock.patch.object(hub, "_ensure_listener"):
            res = await client.get(STREAM)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res["Content-Type"], "text/event-stream; charset=utf-8")
            self.assertEqual(res["X-Accel-Buffering"], "no")
            chunks = res.streaming_content.__aiter__()

            async def next_event(timeout=5):
                return (await asyncio.wait_for(anext(chunks), timeout=timeout)).decode()

            self.assertIn("retry:", await next_event())
            ready = await next_event()
            self.assertIn("event: ready", ready)
            self.assertIn('"unread": 1', ready)

            # NOTIFY доставлен: Hub кладёт событие в очередь подписчика
            n = await sync_to_async(self.create)(self.alice, "Приказ подписан")
            hub.dispatch(json.dumps({"user_id": self.alice.id, "id": n.id}))
            event = await next_event()
            self.assertIn("event: notification", event)
            self.assertIn("Приказ подписан", event)
            self.assertIn('"unread": 2', event)

            # чужое уведомление (id другого пользователя) в поток не попадает
            foreign = await sync_to_async(self.create)(self.bob, "чужое")
            hub.dispatch(json.dumps({"user_id": self.alice.id, "id": foreign.id}))
            with self.assertRaises(asyncio.TimeoutError):
                await next_event(timeout=0.5)
            await chunks.aclose()
        self.assertNotIn(self.alice.id, hub.subscribers)  # соединение закрыто → подписка снята
