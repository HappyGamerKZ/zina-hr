"""Клиент локальной модели Ollama (по умолчанию llama3.1:8b).

Ollama запускается отдельно: на компьютере (ollama.com, `ollama pull llama3.1:8b`) или
сервисом `ollama` в docker compose (профиль ai). Адрес и модель — в .env: OLLAMA_URL, OLLAMA_MODEL.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings


class AssistantUnavailable(Exception):
    """Модель не ответила: Ollama не запущена, модель не скачана или истёк таймаут."""


def chat(messages: list[dict]) -> str:
    body = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        # низкая температура — меньше «фантазий»; 4096 токенов хватает на фрагменты базы и экономит память
        "options": {"temperature": 0.2, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        settings.OLLAMA_URL.rstrip("/") + "/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise AssistantUnavailable(f"Ollama → HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise AssistantUnavailable(f"Ollama недоступна ({settings.OLLAMA_URL}): {exc}") from exc
    answer = (data.get("message") or {}).get("content", "").strip()
    if not answer:
        raise AssistantUnavailable("Ollama вернула пустой ответ")
    return answer
