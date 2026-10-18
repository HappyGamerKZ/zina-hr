from django.conf import settings
from django.db import models


class AssistantQuestion(models.Model):
    """Вопрос, на который AI Jana не ответила и сотрудник передал его в HR («Передать в HR»)."""

    class QStatus(models.TextChoices):
        OPEN = "open", "Ждёт ответа HR"
        ANSWERED = "answered", "Отвечен"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="сотрудник", on_delete=models.CASCADE,
                             related_name="assistant_questions")
    question = models.TextField("вопрос")
    ai_answer = models.TextField("ответ AI Jana", blank=True)
    lang = models.CharField("язык", max_length=2, default="ru")
    status = models.CharField("статус", max_length=16, choices=QStatus.choices, default=QStatus.OPEN)
    hr_answer = models.TextField("ответ HR", blank=True)
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ответил", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    answered_at = models.DateTimeField("когда ответил", null=True, blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "вопрос из AI Jana"
        verbose_name_plural = "вопросы из AI Jana"
        ordering = ["-created_at"]

    def __str__(self):
        return self.question[:80]
