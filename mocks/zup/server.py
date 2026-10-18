"""Заглушка HTTP-сервиса 1С:ЗУП для JanaHR (только стандартная библиотека Python).

Контракт — тот же, что должен реализовать HTTP-сервис в настоящей 1С:ЗУП (публикация /hs/janamen/v1).
Для боевого подключения в backend меняются только ZUP_BASE_URL, ZUP_USER, ZUP_PASSWORD.

    GET  /hs/janamen/v1/snapshot   → компания, подразделения, должности, сотрудники, остатки отпуска
    POST /hs/janamen/v1/vacations  → создать документ «Отпуск», списать дни; ответ {"document_id": ...}
    GET  /hs/janamen/v1/vacations  → созданные документы (для проверки)

Только для демо (в настоящей ЗУП их нет):
    PATCH /__mock/employees/<табельный №>  {"position_code": "...", ...} — «кадровик изменил данные в 1С»
    POST  /__mock/reset                     — вернуть данные из data.json
    GET   /health
Авторизация: Basic (ZUP_USER / ZUP_PASSWORD); если пароль не задан — без проверки.
"""
import base64
import copy
import json
import os
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_FILE = os.environ.get("DATA_FILE", os.path.join(os.path.dirname(__file__), "data.json"))
USER = os.environ.get("ZUP_USER", "janamen")
PASSWORD = os.environ.get("ZUP_PASSWORD", "")
PORT = int(os.environ.get("PORT", "8001"))

lock = threading.Lock()
state: dict = {}


def load() -> None:
    with open(DATA_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    with lock:
        state.clear()
        state.update(data)
        state["vacations"] = []


class Handler(BaseHTTPRequestHandler):
    server_version = "MockZUP/1.0"

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
        if not PASSWORD:
            return True
        expected = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
        return self.headers.get("Authorization") == f"Basic {expected}"

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        with lock:
            if self.path == "/hs/janamen/v1/snapshot":
                snap = {k: copy.deepcopy(v) for k, v in state.items() if k != "vacations"}
                return self._send(200, snap)
            if self.path == "/hs/janamen/v1/vacations":
                return self._send(200, {"items": state["vacations"]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/__mock/reset":
            load()
            return self._send(200, {"status": "reset"})
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/hs/janamen/v1/vacations":
            body = self._body()
            missing = [k for k in ("tab_number", "date_from", "date_to", "days") if k not in body]
            if missing:
                return self._send(400, {"error": f"не хватает полей: {', '.join(missing)}"})
            with lock:
                # повторная отправка той же заявки не создаёт второй документ (идемпотентность)
                for doc in state["vacations"]:
                    if body.get("request_number") and doc["request_number"] == body.get("request_number"):
                        return self._send(200, {"document_id": doc["document_id"], "duplicate": True})
                doc_id = f"ZUP-ОТП-{date.today():%Y}-{len(state['vacations']) + 1:05d}"
                state["vacations"].append({**body, "document_id": doc_id})
                if body.get("vacation_type", "annual") == "annual":
                    for bal in state.get("leave_balances", []):
                        if bal["tab_number"] == body["tab_number"] and bal.get("leave_type", "annual") == "annual":
                            bal["days_used"] += int(body["days"])
                            bal["as_of"] = date.today().isoformat()
            return self._send(201, {"document_id": doc_id})
        self._send(404, {"error": "not found"})

    def do_PATCH(self):
        prefix = "/__mock/employees/"
        if self.path.startswith(prefix):
            tab = self.path[len(prefix):]
            body = self._body()
            with lock:
                for emp in state.get("employees", []):
                    if emp["tab_number"] == tab:
                        emp.update({k: v for k, v in body.items() if k != "tab_number"})
                        return self._send(200, emp)
            return self._send(404, {"error": "employee not found"})
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(f"[mock-zup] {self.command} {self.path} → {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    load()
    print(f"[mock-zup] 1С:ЗУП (заглушка) на :{PORT}, сотрудников: {len(state.get('employees', []))}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
