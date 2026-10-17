"""Реализации интерфейсов из ports.py.

*_http — ходят по HTTP. В docker compose это заглушки mocks/zup и mocks/documentolog,
в бою — те же адреса у настоящего HTTP-сервиса 1С:ЗУП и API Documentolog (меняются URL и ключи в .env).
inmemory — без сети: для тестов и запуска без заглушек.
"""
import itertools
from datetime import date

from django.conf import settings
from django.utils import timezone

from integrations.http import request_json
from integrations.ports import (
    IntegrationError,
    ZupDepartment,
    ZupEmployee,
    ZupLeaveBalance,
    ZupPosition,
    ZupSnapshot,
)


# --- бухгалтерия ---

class MockAccountingAdapter:
    """Заглушка бухгалтерии: «принимает» заявку и выдаёт номер документа."""

    name = "mock_accounting"

    def send_request(self, payload: dict) -> str:
        from integrations.models import AccountingExport

        seq = AccountingExport.objects.filter(provider=self.name).count() + 1
        return f"BUH-{timezone.now():%Y}-{seq:05d}"


# --- 1С:ЗУП ---

def _snapshot_from_json(data: dict) -> ZupSnapshot:
    company = data["company"]
    return ZupSnapshot(
        company_code=company["code"],
        company_name_ru=company["name_ru"],
        company_name_kk=company.get("name_kk", ""),
        departments=[
            ZupDepartment(d["code"], d["name_ru"], d.get("name_kk", ""), d.get("parent_code"))
            for d in data.get("departments", [])
        ],
        positions=[ZupPosition(p["code"], p["title_ru"], p.get("title_kk", "")) for p in data.get("positions", [])],
        employees=[
            ZupEmployee(
                tab_number=e["tab_number"], full_name=e["full_name"], department_code=e["department_code"],
                position_code=e["position_code"], hire_date=date.fromisoformat(e["hire_date"]),
                manager_tab_number=e.get("manager_tab_number"), email=e.get("email", ""),
            )
            for e in data.get("employees", [])
        ],
        balances=[
            ZupLeaveBalance(
                tab_number=b["tab_number"], days_total=int(b["days_total"]), days_used=int(b["days_used"]),
                as_of=date.fromisoformat(b["as_of"]), leave_type=b.get("leave_type", "annual"),
            )
            for b in data.get("leave_balances", [])
        ],
    )


class ZupHttpAdapter:
    """HTTP-сервис 1С:ЗУП (публикация /hs/janamen/v1). Контракт описан в mocks/zup/server.py."""

    name = "zup_http"

    def __init__(self):
        self.base = settings.ZUP_BASE_URL.rstrip("/")
        self.auth = (settings.ZUP_USER, settings.ZUP_PASSWORD)

    def fetch_snapshot(self) -> ZupSnapshot:
        data = request_json("GET", f"{self.base}/hs/janamen/v1/snapshot", basic_auth=self.auth, timeout=15)
        try:
            return _snapshot_from_json(data)
        except (KeyError, ValueError, TypeError) as exc:
            raise IntegrationError(f"1С:ЗУП вернула данные в неожиданном формате: {exc}") from exc

    def push_vacation(self, payload: dict) -> str:
        data = request_json("POST", f"{self.base}/hs/janamen/v1/vacations", payload, basic_auth=self.auth)
        if not data.get("document_id"):
            raise IntegrationError("1С:ЗУП не вернула номер документа")
        return data["document_id"]


class InMemoryZupAdapter:
    """Без сети. Тесты кладут снимок в InMemoryZupAdapter.snapshot."""

    name = "inmemory"
    snapshot: ZupSnapshot | None = None
    pushed: list[dict] = []
    _seq = itertools.count(1)

    def fetch_snapshot(self) -> ZupSnapshot:
        if self.snapshot is None:
            raise IntegrationError("1С:ЗУП не подключена (HRIS_PROVIDER=inmemory, снимок не задан)")
        return self.snapshot

    def push_vacation(self, payload: dict) -> str:
        self.pushed.append(payload)
        return f"ZUP-MEM-{next(self._seq):05d}"


# --- Documentolog ---

class DocumentologHttpAdapter:
    """API Documentolog. Контракт описан в mocks/documentolog/server.py."""

    name = "documentolog_http"

    def __init__(self):
        self.base = settings.DOCUMENTOLOG_BASE_URL.rstrip("/")
        self.token = settings.DOCUMENTOLOG_TOKEN

    def create_document(self, payload: dict, callback_url: str) -> str:
        data = request_json(
            "POST", f"{self.base}/api/v1/documents", {**payload, "callback_url": callback_url}, bearer=self.token
        )
        if not data.get("id"):
            raise IntegrationError("Documentolog не вернул id документа")
        return data["id"]


class InMemoryDocflowAdapter:
    name = "inmemory"
    created: list[dict] = []
    _seq = itertools.count(1)

    def create_document(self, payload: dict, callback_url: str) -> str:
        self.created.append({**payload, "callback_url": callback_url})
        return f"DL-MEM-{next(self._seq):05d}"


ACCOUNTING_PROVIDERS = {MockAccountingAdapter.name: MockAccountingAdapter}
HRIS_PROVIDERS = {ZupHttpAdapter.name: ZupHttpAdapter, InMemoryZupAdapter.name: InMemoryZupAdapter}
DOCFLOW_PROVIDERS = {
    DocumentologHttpAdapter.name: DocumentologHttpAdapter,
    InMemoryDocflowAdapter.name: InMemoryDocflowAdapter,
}


def get_hris():
    provider = HRIS_PROVIDERS.get(settings.HRIS_PROVIDER)
    return provider() if provider else None


def get_docflow():
    provider = DOCFLOW_PROVIDERS.get(settings.DOCFLOW_PROVIDER)
    return provider() if provider else None
