"""Черновики заявок из фразы — без модели, правилами. Заявку создаёт и отправляет только сотрудник.

Отпуск («отпуск» / «демалыс» в тексте):
    с 3 по 14 ноября · 3–14 ноября · с 28 декабря по 5 января · 3-тен 14 қарашаға дейін
    03.11–14.11 · с 3.11.2026 по 14.11.2026 · с 3 по 14 (месяц — ближайший подходящий)
    на следующей неделе · келесі аптада                         → пн–вс следующей недели
    завтра / послезавтра / с понедельника / через неделю / с 10 ноября + «на N дней», «на 2 недели»
    (длительность не указана — 7 дней, и об этом сказано в ответе)
Аванс («аванс» и сумма от 1 000 ₸): аванс 50 000 · аванс 50к · аванс на 30 тыс · 50 мың аванс
"""
import re
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

from hr_requests.services import vacation_balance

DEFAULT_DAYS = 7  # одна часть отпуска — не короче 7 дней (KB-001)

TEXTS = {
    "ru": {
        "vacation": "Подготовила черновик заявки на отпуск: {date_from} – {date_to}, {days} дн. "
                    "Доступно {available} дн. Проверьте и отправьте его сами — без вашего подтверждения заявка не уйдёт.",
        "assumed": "Длительность не указана — поставила {days} дн., поправьте даты при необходимости.",
        "short": "Недостаточно дней: запрошено {days}, доступно {available}.",
        "advance": "Подготовила черновик заявки на аванс: {amount} ₸. Проверьте сумму и отправьте заявку сами — "
                   "без вашего подтверждения она не уйдёт.",
        "over": "Это больше лимита {max} ₸ — уменьшите сумму перед отправкой.",
    },
    "kk": {
        "vacation": "Демалысқа өтінімнің жобасын дайындадым: {date_from} – {date_to}, {days} күн. "
                    "Қолжетімді {available} күн. Тексеріп, өзіңіз жіберіңіз — сіздің растауыңызсыз өтінім кетпейді.",
        "assumed": "Ұзақтығы көрсетілмеген — {days} күн қойдым, қажет болса күндерді түзетіңіз.",
        "short": "Күн жеткіліксіз: сұралғаны {days}, қолжетімдісі {available}.",
        "advance": "Авансқа өтінімнің жобасын дайындадым: {amount} ₸. Соманы тексеріп, өтінімді өзіңіз жіберіңіз — "
                   "сіздің растауыңызсыз ол кетпейді.",
        "over": "Бұл {max} ₸ шегінен көп — жібермес бұрын соманы азайтыңыз.",
    },
}

MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6, "июл": 7, "август": 8, "сентябр": 9,
    "октябр": 10, "ноябр": 11, "декабр": 12,
    "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4, "мамыр": 5, "маусым": 6, "шілде": 7, "тамыз": 8,
    "қыркүйек": 9, "қазан": 10, "қараша": 11, "желтоқсан": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
KK_FROM = r"(?:-?(?:тен|ден|нан|нен|тан|дан))"  # казахский исходный падеж: «3-тен», «дүйсенбіден»

NUMBER_WORDS = {
    "один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7,
    "восемь": 8, "девять": 9, "десять": 10, "четырнадцать": 14,
    "бір": 1, "екі": 2, "үш": 3, "төрт": 4, "бес": 5, "алты": 6, "жеті": 7, "сегіз": 8, "тоғыз": 9, "он": 10,
}
NUM = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
WEEKDAYS = {
    "понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4, "суббот": 5, "воскресен": 6,
    "дүйсенбі": 0, "сейсенбі": 1, "сәрсенбі": 2, "бейсенбі": 3, "жұма": 4, "жексенбі": 6, "сенбі": 5,
}
WEEKDAY_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))

VACATION_INTENT = re.compile(r"отпуск|демалыс", re.I)
ADVANCE_INTENT = re.compile(r"аванс", re.I)

# (?<!\d)…(?!\d) — число целиком: иначе «10 ноября» читалось бы как диапазон «1–0 ноября»
D = r"(?<!\d)(\d{1,2})(?!\d)"
R_MONTH_RANGE = re.compile(
    rf"{D}{KK_FROM}?(?:\s*({MONTH_RE})\w*)?\s*(?:по|до|-|–|—)?\s*{D}\s*({MONTH_RE})\w*")
R_NUMERIC_RANGE = re.compile(
    rf"{D}[./](\d{{1,2}})(?:[./](\d{{2,4}}))?\s*(?:по|до|-|–|—)\s*{D}[./](\d{{1,2}})(?:[./](\d{{2,4}}))?")
R_DAY_RANGE = re.compile(rf"(?:\bс\s*(\d{{1,2}})\s*(?:по|до)\s*(\d{{1,2}})\b(?!\s*[./]))|"
                         rf"(?:(\d{{1,2}}){KK_FROM}\s*(\d{{1,2}})\S*\s*дейін)")
R_NEXT_WEEK = re.compile(r"(?:на\s+)?след(?:ующ\w*|\.)?\s+недел\w*|келесі\s+апта\w*")
R_AFTER = re.compile(rf"через\s+{NUM}?\s*(дн\w*|день|недел\w*)|"
                     rf"{NUM}\s*(күн|апта)\w*?(?:дан|ден|тан|тен|нан|нен)\s+кейін")
R_WEEKDAY = re.compile(rf"(?:\bс\s+|\bсо\s+)({WEEKDAY_RE})\w*|({WEEKDAY_RE}){KK_FROM}")
R_START_DATE = re.compile(rf"(?:\bс\s*)?{D}\s*({MONTH_RE})\w*|{D}[./](\d{{1,2}})(?:[./](\d{{2,4}}))?")
R_DURATION_DAYS = re.compile(rf"\bна\s+{NUM}\s*(?:дн\w*|день)|{NUM}\s*күн(?:ге|дік)?\b")
R_DURATION_WEEKS = re.compile(rf"\bна\s+(?:{NUM}\s*)?недел\w*|(?:{NUM}\s*)?аптаға\b")


def _num(token: str | None, default: int = 1) -> int:
    if not token:
        return default
    return int(token) if token.isdigit() else NUMBER_WORDS.get(token, default)


def _month(word: str) -> int:  # длинные основы первыми: «маусым» — июнь, а не «ма(й)»
    return next(MONTHS[k] for k in sorted(MONTHS, key=len, reverse=True) if word.startswith(k))


def _year(token: str | None, default: int) -> int:
    if not token:
        return default
    y = int(token)
    return 2000 + y if y < 100 else y


def _next_weekday(today: date, weekday: int) -> date:
    return today + timedelta(days=(weekday - today.weekday() - 1) % 7 + 1)  # строго после сегодня


def _explicit_range(t: str, today: date) -> tuple[date, date] | None:
    m = R_MONTH_RANGE.search(t)
    if m:
        end_month = _month(m.group(4))
        start_month = _month(m.group(2)) if m.group(2) else end_month
        start = date(today.year, start_month, int(m.group(1)))
        if start < today:
            start = date(today.year + 1, start_month, int(m.group(1)))
        return start, date(start.year + (1 if end_month < start_month else 0), end_month, int(m.group(3)))
    m = R_NUMERIC_RANGE.search(t)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        start = date(_year(y1, today.year), int(m1), int(d1))
        if start < today and not y1:
            start = date(today.year + 1, int(m1), int(d1))
        end = date(_year(y2, start.year + (1 if int(m2) < int(m1) else 0)), int(m2), int(d2))
        return start, end
    m = R_DAY_RANGE.search(t)
    if m:
        d1, d2 = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
        month_start = date(today.year, today.month, 1)
        if d1 < today.day:  # день уже прошёл — следующий месяц
            month_start = (month_start + timedelta(days=32)).replace(day=1)
        start = month_start.replace(day=d1)
        end_month = start if d2 >= d1 else (start.replace(day=1) + timedelta(days=32)).replace(day=1)
        return start, end_month.replace(day=d2)
    return None


def _duration(t: str) -> int | None:
    m = R_DURATION_WEEKS.search(t)
    if m:
        return 7 * _num(m.group(1) or m.group(2))
    m = R_DURATION_DAYS.search(t)
    if m:
        return _num(m.group(1) or m.group(2))
    return None


def _start_anchor(t: str, today: date) -> tuple[date, date | None] | None:
    """Начало (и для «следующей недели» — сразу конец)."""
    if R_NEXT_WEEK.search(t):
        start = _next_weekday(today, 0)
        return start, start + timedelta(days=6)
    if re.search(r"послезавтра|бүрсігүні", t):
        return today + timedelta(days=2), None
    if re.search(r"завтра|ертең", t):
        return today + timedelta(days=1), None
    m = R_AFTER.search(t)
    if m:
        n, unit = (m.group(1), m.group(2)) if m.group(2) else (m.group(3), m.group(4))
        step = 7 if unit.startswith(("недел", "апта")) else 1
        return today + timedelta(days=step * _num(n)), None
    m = R_WEEKDAY.search(t)
    if m:
        word = m.group(1) or m.group(2)
        day = next(v for k, v in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])) if word.startswith(k))
        return _next_weekday(today, day), None
    m = R_START_DATE.search(t)
    if m:
        if m.group(1):
            start = date(today.year, _month(m.group(2)), int(m.group(1)))
            explicit_year = False
        else:
            start = date(_year(m.group(5), today.year), int(m.group(4)), int(m.group(3)))
            explicit_year = bool(m.group(5))
        if start < today and not explicit_year:
            start = start.replace(year=start.year + 1)
        return start, None
    return None


def parse_vacation_period(text: str, today: date | None = None) -> tuple[date, date, bool] | None:
    """(начало, конец, длительность_додумана) или None, если в тексте нет отпуска с датами."""
    if not VACATION_INTENT.search(text):
        return None
    t = text.lower()
    today = today or timezone.localdate()
    try:
        explicit = _explicit_range(t, today)
        if explicit:
            start, end = explicit
            assumed = False
        else:
            anchor = _start_anchor(t, today)
            if anchor is None:
                return None
            start, end = anchor
            days = _duration(t)
            assumed = end is None and days is None
            if days:
                end = start + timedelta(days=days - 1)
            elif end is None:
                end = start + timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:  # 31 ноября и подобное
        return None
    if start < today or end < start:
        return None
    return start, end, assumed


def parse_vacation_dates(text: str, today: date | None = None) -> tuple[date, date] | None:
    period = parse_vacation_period(text, today)
    return (period[0], period[1]) if period else None


R_AMOUNT = re.compile(r"(?<!\d)(\d{1,3}(?:[  ]\d{3})+|\d+)(?!\d)\s*(тыс\w*|т\.|к\b|k\b|мың)?", re.I)


def parse_advance_amount(text: str) -> int | None:
    """Первая сумма от 1 000 ₸ рядом со словом «аванс»: «50 000», «50к», «30 тыс», «50 мың»."""
    if not ADVANCE_INTENT.search(text):
        return None
    for m in R_AMOUNT.finditer(text):
        value = int(re.sub(r"\D", "", m.group(1)))
        if not m.group(2) and 1900 <= value <= 2100:  # похоже на год, а не сумму
            continue
        if m.group(2):
            value *= 1000
        if value >= 1000:
            return value
    return None


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def vacation_draft(user, question: str, lang: str) -> tuple[dict, str] | None:
    period = parse_vacation_period(question)
    if period is None or user.employee_id is None:
        return None
    start, end, assumed = period
    days = (end - start).days + 1
    available = vacation_balance(user.employee)["days_available"]
    t = TEXTS[lang]
    text = t["vacation"].format(date_from=f"{start:%d.%m.%Y}", date_to=f"{end:%d.%m.%Y}", days=days, available=available)
    if assumed:
        text += " " + t["assumed"].format(days=days)
    if days > available:
        text += " " + t["short"].format(days=days, available=available)
    draft = {"type": "vacation", "date_from": start.isoformat(), "date_to": end.isoformat(), "days": days,
             "available": available}
    return draft, text


def advance_draft(user, question: str, lang: str) -> tuple[dict, str] | None:
    amount = parse_advance_amount(question)
    if amount is None or user.employee_id is None:
        return None
    limit = settings.ADVANCE_MAX_AMOUNT
    t = TEXTS[lang]
    text = t["advance"].format(amount=_money(amount))
    if amount > limit:
        text += " " + t["over"].format(max=_money(limit))
    return {"type": "advance", "amount": amount, "max": limit}, text
