"""Демо-данные подбора: вакансии и кандидаты на всех этапах. Люди вымышленные, контакты — example.com."""
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.utils import timezone

from recruitment.models import (
    Candidate, CandidateEvent, EmploymentType, Interview, InterviewKind, Stage, Vacancy, VacancyStatus,
)

A = CandidateEvent.Action
# Шрифт Helvetica в PDF без кириллицы — в демо-резюме позиции латиницей
POSITION_EN = {"Логист": "Logistics specialist", "Оператор отделения": "Branch operator", "HR-специалист": "HR specialist"}


def make_pdf(lines: list[str]) -> bytes:
    """Минимальный корректный PDF (латиница, шрифт Helvetica) — чтобы демо-резюме открывались в браузере."""
    text = "BT /F1 14 Tf 72 760 Td 18 TL " + " ".join(
        "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for line in lines
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out.encode("latin-1")))
        out += f"{i} 0 obj\n{body}\nendobj\n"
    xref = len(out.encode("latin-1"))
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def create_demo_recruitment(u: dict, e: dict) -> None:
    """u — пользователи по логинам, e — сотрудники (из core.demo_users)."""
    Candidate.objects.all().delete()
    Vacancy.objects.all().delete()
    today = timezone.localdate()

    def at(days: int, hour: int, minute: int = 0):
        return timezone.make_aware(datetime.combine(today + timedelta(days=days), time(hour, minute)))

    logist = Vacancy.objects.create(
        title_ru="Логист", title_kk="Логист", department=e["employee"].department,
        hiring_manager=e["manager_logistics"], description="Планирование доставок Китай → Казахстан → ЦА.",
        salary_from=400_000, salary_to=520_000,
    )
    operator = Vacancy.objects.create(
        title_ru="Оператор отделения", title_kk="Бөлімше операторы", department=e["employee_service"].department,
        hiring_manager=e["manager_service"], description="Выдача и приём посылок, работа с клиентами.",
        salary_from=250_000, salary_to=320_000, employment_type=EmploymentType.PART_TIME,
    )
    hr_vacancy = Vacancy.objects.create(
        title_ru="HR-специалист", title_kk="HR-маман", department=e["hr_spec_1"].department,
        hiring_manager=e["head_hr"], description="Кадровое делопроизводство и адаптация сотрудников.",
    )
    Vacancy.objects.create(
        title_ru="Курьер", title_kk="Курьер", department=e["employee"].department, hiring_manager=e["manager_logistics"],
        description="Доставка посылок по Алматы.", salary_from=280_000, salary_to=350_000,
        status=VacancyStatus.CLOSED,
    )
    Vacancy.objects.create(
        title_ru="Аналитик данных", title_kk="Деректер талдаушысы", department=e["hr_spec_1"].department,
        hiring_manager=e["head_hr"], description="HR-аналитика и отчёты для руководства.",
        employment_type=EmploymentType.CONTRACT, status=VacancyStatus.DRAFT,
    )

    def candidate(name, latin, vacancy, stage, salary, days_ago, *, reviewed=False, decision="", pdf=True,
                  profile="", social=""):
        c = Candidate(
            vacancy=vacancy, full_name=name, email=f"{latin.split()[0].lower()}@example.com",
            phone=f"+7 700 000 {days_ago:02d} {salary // 10000:02d}", social=social, profile_url=profile,
            expected_salary=salary, stage=stage, decision_stage=decision,
            consent_at=timezone.now() - timedelta(days=days_ago),
            reviewed_at=timezone.now() - timedelta(days=days_ago - 1) if reviewed else None,
            comment="Готов(а) приступить через 2 недели.",
        )
        if pdf:
            c.resume_pdf.save(
                f"demo-{latin.split()[0].lower()}.pdf",
                ContentFile(make_pdf([f"Resume: {latin}", f"Position: {POSITION_EN.get(vacancy.title_ru, '')}",
                                      "Experience: 3 years in logistics and customer service",
                                      "Languages: Kazakh, Russian, English", "Demo resume for JanaMen prototype"])),
                save=False,
            )
        c.save()
        Candidate.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        CandidateEvent.objects.create(candidate=c, action=A.SUBMITTED, stage=Stage.SCREENING)
        return c

    def decided(c, action, days_ago, comment=""):
        ev = CandidateEvent.objects.create(candidate=c, action=action, stage=c.stage, actor=u["hr_spec_1"], comment=comment)
        CandidateEvent.objects.filter(pk=ev.pk).update(created_at=timezone.now() - timedelta(days=days_ago))

    def interview(c, kind, when, interviewer, location, status=Interview.InterviewStatus.SCHEDULED, feedback=""):
        Interview.objects.create(candidate=c, kind=kind, scheduled_at=when, interviewer=interviewer, location=location,
                                 status=status, feedback=feedback, created_by=u["hr_spec_1"])

    # 1. Новое резюме, ещё не просмотрено
    candidate("Тулегенов Ержан Маратович", "Yerzhan Tulegenov", logist, Stage.SCREENING, 450_000, 1,
              social="@yerzhan_t")
    # 2. Просмотрено (галочка скрининга), решение ещё не принято; вместо PDF — профиль hh.kz
    candidate("Асанова Мадина Ерлановна", "Madina Asanova", operator, Stage.SCREENING, 300_000, 3, reviewed=True,
              pdf=False, profile="https://hh.kz/resume/demo-madina", social="instagram.com/madina.demo")
    # 3. HR-интервью назначено на завтра
    c = candidate("Касымов Даурен Болатович", "Dauren Kassymov", logist, Stage.HR_INTERVIEW, 500_000, 6, reviewed=True)
    interview(c, InterviewKind.HR, at(1, 11), u["hr_spec_1"], "Переговорная 3, офис Алматы")
    # 4. Техническое интервью с руководителем логистики через 2 дня
    c = candidate("Ахметов Тимур Русланович", "Timur Akhmetov", logist, Stage.TECH_INTERVIEW, 550_000, 10, reviewed=True)
    interview(c, InterviewKind.HR, at(-3, 10), u["hr_spec_2"], "Zoom", Interview.InterviewStatus.DONE,
              "Мотивирован, опыт с таможней. Рекомендую на техинтервью.")
    interview(c, InterviewKind.TECH, at(2, 15), u["manager_logistics"], "Zoom: ссылка придёт в календарь")
    # 5. HR-специалист: техинтервью с head_hr
    c = candidate("Нуриева Алия Сериковна", "Aliya Nurieva", hr_vacancy, Stage.TECH_INTERVIEW, 400_000, 8, reviewed=True)
    interview(c, InterviewKind.TECH, at(3, 12), u["head_hr"], "Кабинет HR")
    # 6. Отказ после HR-интервью
    c = candidate("Жанибекова Сауле Аскаровна", "Saule Zhanibekova", operator, Stage.REJECTED, 350_000, 14,
              reviewed=True, decision=Stage.HR_INTERVIEW)
    decided(c, A.REJECTED, 10, "Нет опыта работы с клиентами")
    # 7. Принят после техинтервью
    c = candidate("Сейтказы Арман Нурланович", "Arman Seitkazy", logist, Stage.HIRED, 480_000, 21,
              reviewed=True, decision=Stage.TECH_INTERVIEW)
    decided(c, A.HIRED, 5)
