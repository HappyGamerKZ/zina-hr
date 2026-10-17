import logging

from django.conf import settings

from integrations.adapters import PROVIDERS
from integrations.models import AccountingExport
from integrations.ports import AccountingProvider

logger = logging.getLogger(__name__)


def get_accounting_provider() -> AccountingProvider:
    return PROVIDERS[settings.ACCOUNTING_PROVIDER]()


def build_accounting_payload(req) -> dict:
    payload = {
        "request_number": req.number,
        "type": req.type,
        "employee_tab_number": req.employee.external_id,
        "employee_name": req.employee.full_name,
    }
    if req.type == "vacation":
        v = req.vacation
        payload.update(
            date_from=v.date_from.isoformat(), date_to=v.date_to.isoformat(),
            days=v.days, vacation_type=v.vacation_type,
        )
    else:
        payload.update(amount=str(req.advance.amount), reason=req.advance.reason)
    return payload


def send_to_accounting(req) -> AccountingExport:
    """Передать утверждённую заявку в бухгалтерию. Ошибка не роняет утверждение — она пишется в журнал."""
    provider = get_accounting_provider()
    payload = build_accounting_payload(req)
    try:
        external_id = provider.send_request(payload)
    except Exception as exc:  # внешняя система недоступна — HR увидит ошибку в админке
        logger.exception("Accounting export failed for %s", req.number)
        return AccountingExport.objects.create(
            request=req, provider=provider.name, payload=payload,
            status=AccountingExport.ExportStatus.FAILED, error=str(exc),
        )
    return AccountingExport.objects.create(
        request=req, provider=provider.name, payload=payload,
        status=AccountingExport.ExportStatus.SENT, external_id=external_id,
    )
