import hashlib
import hmac
import json

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import events
from hr_requests.models import HrRequest, RequestEvent

DOC_STATUSES = {"document.signed": "signed", "document.rejected": "rejected"}


def valid_signature(raw: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(settings.DOCUMENTOLOG_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


class DocumentologWebhookView(APIView):
    """Обратный вызов Documentolog: приказ подписан или отклонён.

    Вызывает внешняя система, а не пользователь: сессии нет, подлинность проверяется
    HMAC-подписью тела (X-Documentolog-Signature) общим секретом DOCUMENTOLOG_WEBHOOK_SECRET.
    Повторный вызов с тем же статусом ничего не меняет (идемпотентность).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=inline_serializer("DocumentologEvent", {
            "event": serializers.ChoiceField(choices=list(DOC_STATUSES)),
            "document_id": serializers.CharField(),
            "registration_number": serializers.CharField(required=False),
            "signer": serializers.CharField(required=False),
            "comment": serializers.CharField(required=False),
        }),
        responses={200: None},
    )
    def post(self, request):
        raw = request.body
        if not valid_signature(raw, request.headers.get("X-Documentolog-Signature", "")):
            return Response({"error": "invalid signature"}, status=status.HTTP_403_FORBIDDEN)
        try:
            data = json.loads(raw)
            doc_status = DOC_STATUSES[data["event"]]
            doc_id = data["document_id"]
        except (ValueError, KeyError):
            return Response({"error": "bad payload"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            req = HrRequest.objects.select_for_update().filter(external_doc_id=doc_id).first()
            if req is None:
                return Response({"error": "unknown document"}, status=status.HTTP_404_NOT_FOUND)
            if req.doc_status == doc_status:
                return Response({"status": "already processed"})
            req.doc_status = doc_status
            if doc_status == "signed":
                req.doc_registration_number = data.get("registration_number", "")
                note = f"Documentolog: приказ подписан, рег. № {req.doc_registration_number}"
                if data.get("signer"):
                    note += f" ({data['signer']})"
            else:
                note = f"Documentolog: приказ отклонён — {data.get('comment') or 'без комментария'}"
            req.save(update_fields=["doc_status", "doc_registration_number", "updated_at"])
            RequestEvent.objects.create(request=req, from_status=req.status, to_status=req.status, comment=note)
            transaction.on_commit(lambda: events.publish(events.DOCUMENT_STATUS_CHANGED, request=req))
        return Response({"status": "ok"})
