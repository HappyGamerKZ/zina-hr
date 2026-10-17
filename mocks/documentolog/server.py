"""Заглушка API Documentolog для JanaМен (только стандартная библиотека Python).

    POST /api/v1/documents       создать документ на подпись → {"id", "status": "on_signing"}
    GET  /api/v1/documents/<id>  статус документа
    GET  /api/v1/documents       все документы (для проверки)

Через SIGN_DELAY секунд (по умолчанию 10) документ «подписывается», и заглушка шлёт обратный вызов
на callback_url из запроса. Тело подписано HMAC-SHA256 (заголовок X-Documentolog-Signature: sha256=<hex>)
секретом DOCUMENTOLOG_WEBHOOK_SECRET — backend проверяет подпись.

Только для демо:
    POST /__mock/documents/<id>/reject  {"comment": "..."} — «подписант отклонил приказ»
    GET  /health
Авторизация: Bearer DOCUMENTOLOG_TOKEN; если токен не задан — без проверки.
"""
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8002"))
TOKEN = os.environ.get("DOCUMENTOLOG_TOKEN", "")
SECRET = os.environ.get("DOCUMENTOLOG_WEBHOOK_SECRET", "dev-webhook-secret").encode()
SIGN_DELAY = float(os.environ.get("SIGN_DELAY", "10"))
SIGNER = os.environ.get("SIGNER", "Касымова Д. М., руководитель отдела кадров (демо)")

lock = threading.Lock()
documents: dict[str, dict] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def send_callback(doc: dict, event: str, extra: dict) -> None:
    body = json.dumps({
        "event": event, "document_id": doc["id"], "external_ref": doc.get("external_ref"),
        "status": doc["status"], **extra,
    }, ensure_ascii=False).encode()
    signature = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    for attempt in range(1, 6):  # backend может быть занят — несколько попыток
        try:
            req = urllib.request.Request(doc["callback_url"], data=body, method="POST")
            req.add_header("Content-Type", "application/json; charset=utf-8")
            req.add_header("X-Documentolog-Signature", signature)
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"[mock-documentolog] callback {doc['id']} {event} → {resp.status}", flush=True)
                return
        except Exception as exc:  # noqa: BLE001
            print(f"[mock-documentolog] callback {doc['id']} попытка {attempt}: {exc}", flush=True)
            time.sleep(5)


def auto_sign(doc_id: str) -> None:
    time.sleep(SIGN_DELAY)
    with lock:
        doc = documents[doc_id]
        if doc["status"] != "on_signing":
            return
        doc.update(status="signed", signed_at=now_iso(), signer=SIGNER,
                   registration_number=f"{doc['seq']}-к/{datetime.now():%Y}")
        snapshot = dict(doc)
    send_callback(snapshot, "document.signed", {
        "registration_number": snapshot["registration_number"], "signed_at": snapshot["signed_at"],
        "signer": snapshot["signer"],
    })


class Handler(BaseHTTPRequestHandler):
    server_version = "MockDocumentolog/1.0"

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _authorized(self) -> bool:
        return not TOKEN or self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        with lock:
            if self.path == "/api/v1/documents":
                return self._send(200, {"items": list(documents.values())})
            if self.path.startswith("/api/v1/documents/"):
                doc = documents.get(self.path.rsplit("/", 1)[-1])
                return self._send(200, doc) if doc else self._send(404, {"error": "not found"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/__mock/documents/") and self.path.endswith("/reject"):
            doc_id = self.path.split("/")[3]
            comment = self._body().get("comment", "Отклонено подписантом")
            with lock:
                doc = documents.get(doc_id)
                if not doc:
                    return self._send(404, {"error": "not found"})
                doc.update(status="rejected", comment=comment)
                snapshot = dict(doc)
            threading.Thread(target=send_callback, args=(snapshot, "document.rejected", {"comment": comment}),
                             daemon=True).start()
            return self._send(200, snapshot)
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/api/v1/documents":
            body = self._body()
            if not body.get("callback_url") or not body.get("title"):
                return self._send(400, {"error": "нужны title и callback_url"})
            with lock:
                # повторная отправка того же приказа не создаёт второй документ (идемпотентность)
                for doc in documents.values():
                    if body.get("external_ref") and doc.get("external_ref") == body["external_ref"] \
                            and doc.get("template") == body.get("template"):
                        return self._send(200, {"id": doc["id"], "status": doc["status"], "duplicate": True})
                seq = len(documents) + 1
                doc_id = f"DL-{datetime.now():%Y}-{seq:06d}"
                documents[doc_id] = {**body, "id": doc_id, "seq": seq, "status": "on_signing", "created_at": now_iso()}
            threading.Thread(target=auto_sign, args=(doc_id,), daemon=True).start()
            return self._send(201, {"id": doc_id, "status": "on_signing"})
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(f"[mock-documentolog] {self.command} {self.path} → {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    print(f"[mock-documentolog] Documentolog (заглушка) на :{PORT}, подпись через {SIGN_DELAY:g} с", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
