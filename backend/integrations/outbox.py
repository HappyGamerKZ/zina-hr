"""Outbox: доставка утверждённых заявок во внешние системы.

1. При утверждении заявки в той же транзакции создаются задачи OutboxTask (по одной на систему).
2. Сразу после коммита — быстрая попытка отправить их (обычно всё уходит за доли секунды).
3. Что не ушло (система недоступна) — повторяет worker (manage.py run_worker) с нарастающей паузой.
4. Каждая доставка — событие в истории заявки; заявка остаётся «Утверждено / Передано в 1С».

Маршрут по типам заявки:
    отпуск → 1С / бухгалтерия (отпускные), 1С:ЗУП (документ «Отпуск»), Documentolog (приказ)
    аванс  → 1С / бухгалтерия (выплата), Documentolog (приказ)
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from integrations import services as accounting
from integrations.adapters import get_docflow, get_hris
from integrations.models import OutboxTask
from integrations.ports import IntegrationError

logger = logging.getLogger(__name__)
Target = OutboxTask.Target

TEMPLATES = {
    "vacation": ("vacation_order", "Приказ о предоставлении отпуска"),
    "advance": ("advance_order", "Приказ о выплате аванса"),
}


def targets_for(req) -> list[str]:
    targets = [Target.ACCOUNTING]
    if req.type == "vacation" and get_hris() is not None:
        targets.append(Target.ZUP)
    if get_docflow() is not None:
        targets.append(Target.DOCUMENTOLOG)
    return targets


def enqueue_approved(req) -> list[OutboxTask]:
    """Вызывается внутри транзакции утверждения заявки."""
    tasks = [OutboxTask.objects.get_or_create(request=req, target=t)[0] for t in targets_for(req)]
    ids = [t.id for t in tasks]
    transaction.on_commit(lambda: dispatch(ids))
    return tasks


def dispatch(task_ids: list[int]) -> None:
    """Быстрая попытка сразу после утверждения. Ошибки не пробрасываются — повторит worker."""
    for task_id in task_ids:
        try:
            deliver(task_id)
        except Exception:  # noqa: BLE001 — сбой отправки не должен ломать ответ пользователю
            logger.exception("Outbox: не удалось обработать задачу %s", task_id)


def backoff(attempts: int) -> timedelta:
    """30 с, 1 мин, 2 мин, 4 мин … но не больше 30 мин."""
    return timedelta(seconds=min(30 * 2 ** (attempts - 1), 1800))


# --- отправка в каждую систему: возвращает (номер во внешней системе, текст для истории заявки) ---

def _send_accounting(req) -> tuple[str, str]:
    export = accounting.send_to_accounting(req)
    if export.status != export.ExportStatus.SENT:
        raise IntegrationError(export.error or "бухгалтерия не приняла документ")
    req.external_accounting_id = export.external_id
    req.save(update_fields=["external_accounting_id", "updated_at"])
    return export.external_id, f"1С / бухгалтерия: документ № {export.external_id}"


def _send_zup(req) -> tuple[str, str]:
    hris = get_hris()
    if hris is None:
        raise IntegrationError("Интеграция с 1С:ЗУП отключена")
    v = req.vacation
    doc_id = hris.push_vacation({
        "request_number": req.number,
        "tab_number": req.employee.external_id,
        "full_name": req.employee.full_name,
        "date_from": v.date_from.isoformat(),
        "date_to": v.date_to.isoformat(),
        "days": v.days,
        "vacation_type": v.vacation_type,
    })
    req.external_zup_id = doc_id
    req.save(update_fields=["external_zup_id", "updated_at"])
    return doc_id, f"1С:ЗУП: документ «Отпуск» № {doc_id}"


def _send_documentolog(req) -> tuple[str, str]:
    docflow = get_docflow()
    if docflow is None:
        raise IntegrationError("Интеграция с Documentolog отключена")
    template, title = TEMPLATES[req.type]
    doc_id = docflow.create_document(
        {
            "template": template,
            "title": f"{title}: {req.employee.full_name}",
            "external_ref": req.number,
            "employee": {"tab_number": req.employee.external_id, "full_name": req.employee.full_name},
            "payload": accounting.build_accounting_payload(req),
        },
        callback_url=f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/v1/integrations/documentolog/webhook",
    )
    req.external_doc_id = doc_id
    req.doc_status = "on_signing"
    req.save(update_fields=["external_doc_id", "doc_status", "updated_at"])
    return doc_id, f"Documentolog: приказ отправлен на подпись (№ {doc_id})"


SENDERS = {Target.ACCOUNTING: _send_accounting, Target.ZUP: _send_zup, Target.DOCUMENTOLOG: _send_documentolog}


def deliver(task_id: int) -> OutboxTask | None:
    """Отправить одну задачу. Задачу, которую уже обрабатывает другой процесс, пропускаем."""
    from hr_requests.models import RequestEvent

    with transaction.atomic():
        task = (
            OutboxTask.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("request__employee")
            .filter(pk=task_id, status=OutboxTask.TaskStatus.PENDING)
            .first()
        )
        if task is None:
            return None
        req = task.request
        task.attempts += 1
        try:
            external_id, note = SENDERS[task.target](req)
        except Exception as exc:  # noqa: BLE001 — любой сбой внешней системы → повтор позже
            task.last_error = str(exc)[:1000]
            if task.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
                task.status = OutboxTask.TaskStatus.FAILED
            else:
                task.next_attempt_at = timezone.now() + backoff(task.attempts)
            task.save()
            logger.warning("Outbox: %s → %s, попытка %s: %s", req.number, task.target, task.attempts, exc)
            return task
        task.status = OutboxTask.TaskStatus.SENT
        task.external_id = external_id
        task.last_error = ""
        task.sent_at = timezone.now()
        task.save()
        RequestEvent.objects.create(request=req, from_status=req.status, to_status=req.status, comment=note)
        return task


def process_due(limit: int = 20) -> list[OutboxTask]:
    """Для worker: отправить задачи, у которых наступило время следующей попытки."""
    ids = list(
        OutboxTask.objects.filter(status=OutboxTask.TaskStatus.PENDING, next_attempt_at__lte=timezone.now())
        .order_by("next_attempt_at")
        .values_list("id", flat=True)[:limit]
    )
    return [t for t in (deliver(i) for i in ids) if t is not None]


def retry_now(tasks) -> int:
    """Админка: отправить ещё раз (в том числе задачи с закончившимися попытками)."""
    count = tasks.exclude(status=OutboxTask.TaskStatus.SENT).update(
        status=OutboxTask.TaskStatus.PENDING, next_attempt_at=timezone.now(), attempts=0
    )
    return count
