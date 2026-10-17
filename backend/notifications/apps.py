from django.apps import AppConfig
from django.db.models.signals import post_save


class NotificationsConfig(AppConfig):
    name = "notifications"
    verbose_name = "Уведомления"

    def ready(self):
        from notifications import handlers, live
        from notifications.models import Notification

        handlers.register()

        def on_saved(sender, instance, created, **kwargs):
            if created:
                live.notify_created(instance)  # → SSE-поток пользователя (notifications/live.py)

        # weak=False: обработчик — замыкание, без сильной ссылки сборщик мусора удалит его
        post_save.connect(on_saved, sender=Notification, weak=False, dispatch_uid="notifications_live")
