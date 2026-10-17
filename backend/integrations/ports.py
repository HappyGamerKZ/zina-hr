"""Интерфейсы внешних систем. Остальной код знает только о них, а не о конкретной реализации.

Какая реализация используется, задаётся в .env:
    ACCOUNTING_PROVIDER  mock_accounting
    HRIS_PROVIDER        zup_http (заглушка mocks/zup или боевой HTTP-сервис 1С:ЗУП) | inmemory | none
    DOCFLOW_PROVIDER     documentolog_http (заглушка mocks/documentolog или боевой API) | inmemory | none
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class IntegrationError(Exception):
    """Внешняя система недоступна или ответила ошибкой — задачу можно повторить позже."""


# --- 1С:ЗУП: кадровые данные (источник истины) ---

@dataclass
class ZupDepartment:
    code: str
    name_ru: str
    name_kk: str = ""
    parent_code: str | None = None


@dataclass
class ZupPosition:
    code: str
    title_ru: str
    title_kk: str = ""


@dataclass
class ZupEmployee:
    tab_number: str
    full_name: str
    department_code: str
    position_code: str
    hire_date: date
    manager_tab_number: str | None = None
    email: str = ""


@dataclass
class ZupLeaveBalance:
    tab_number: str
    days_total: int
    days_used: int
    as_of: date
    leave_type: str = "annual"


@dataclass
class ZupSnapshot:
    company_code: str
    company_name_ru: str
    company_name_kk: str = ""
    departments: list[ZupDepartment] = field(default_factory=list)
    positions: list[ZupPosition] = field(default_factory=list)
    employees: list[ZupEmployee] = field(default_factory=list)
    balances: list[ZupLeaveBalance] = field(default_factory=list)


class HRISProvider(Protocol):
    """1С:ЗУП. Читаем оргструктуру и остатки отпуска, отправляем утверждённые отпуска."""

    name: str

    def fetch_snapshot(self) -> ZupSnapshot:
        """Сотрудники, подразделения, должности и остатки отпуска одним снимком."""
        ...

    def push_vacation(self, payload: dict) -> str:
        """Создать документ «Отпуск» в ЗУП, вернуть его номер. ЗУП сам спишет дни из остатка."""
        ...


# --- Documentolog: приказы на подпись ---

class DocFlowProvider(Protocol):
    """Documentolog. Отправляем приказ на подпись, результат приходит обратным вызовом (webhook)."""

    name: str

    def create_document(self, payload: dict, callback_url: str) -> str:
        """Создать документ (приказ) на подпись, вернуть его id в Documentolog."""
        ...


# --- Бухгалтерия ---

class AccountingProvider(Protocol):
    """Бухгалтерия: принимает утверждённые заявки на отпуск (отпускные) и аванс (выплата).

    Сейчас — MockAccountingAdapter. Боевой вариант — документ в 1С:Бухгалтерии / 1С:ЗУП
    через HTTP-сервис или OData; выбирается настройкой ACCOUNTING_PROVIDER.
    """

    name: str

    def send_request(self, payload: dict) -> str:
        """Передать заявку, вернуть номер документа в учётной системе."""
        ...
