"""Интерфейсы внешних систем. Остальной код знает только о них, а не о конкретной реализации."""
from typing import Protocol


class AccountingProvider(Protocol):
    """Бухгалтерия: принимает утверждённые заявки на отпуск (отпускные) и аванс (выплата).

    Сейчас — MockAccountingAdapter. Боевой вариант — документ в 1С:Бухгалтерии / 1С:ЗУП
    через HTTP-сервис или OData; выбирается настройкой ACCOUNTING_PROVIDER.
    """

    name: str

    def send_request(self, payload: dict) -> str:
        """Передать заявку, вернуть номер документа в учётной системе."""
        ...
