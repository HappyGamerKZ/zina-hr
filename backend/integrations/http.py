"""Минимальный JSON-клиент на стандартной библиотеке (без лишних зависимостей в образе)."""
import base64
import json
import urllib.error
import urllib.request

from integrations.ports import IntegrationError


def request_json(method: str, url: str, body: dict | None = None, *, timeout: float = 5,
                 basic_auth: tuple[str, str] | None = None, bearer: str | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    if basic_auth:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise IntegrationError(f"{method} {url} → HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IntegrationError(f"{method} {url} недоступен: {exc}") from exc
    try:
        return json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise IntegrationError(f"{method} {url}: ответ не JSON") from exc
