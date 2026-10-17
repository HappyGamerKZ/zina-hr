from django.utils import timezone


class MockAccountingAdapter:
    """Заглушка бухгалтерии: «принимает» заявку и выдаёт номер документа."""

    name = "mock_accounting"

    def send_request(self, payload: dict) -> str:
        from integrations.models import AccountingExport

        seq = AccountingExport.objects.filter(provider=self.name).count() + 1
        return f"BUH-{timezone.now():%Y}-{seq:05d}"


PROVIDERS = {MockAccountingAdapter.name: MockAccountingAdapter}
