// Live-уведомления: подписка на поток GET /api/v1/notifications/stream (Server-Sent Events).
// Браузер сам переподключается после обрыва; пока потока нет, работает обычный опрос.
import { useEffect, useRef, useState } from "react";

/** Возвращает true, пока поток подключён. onNotification вызывается на каждое новое уведомление. */
export function useLiveNotifications(onNotification: () => void): boolean {
  const [connected, setConnected] = useState(false);
  const handler = useRef(onNotification);
  handler.current = onNotification;

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/api/v1/notifications/stream");
    source.addEventListener("ready", () => setConnected(true));
    source.addEventListener("notification", () => handler.current());
    source.onerror = () => setConnected(false); // переподключение — автоматически (retry: 5000)
    return () => source.close();
  }, []);

  return connected;
}
