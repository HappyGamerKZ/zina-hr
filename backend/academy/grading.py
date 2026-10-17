"""Проверка ответов на сервере.

Формат ответа (ключ — id вопроса строкой, как в JSON):
    single       → id варианта                      {"12": 45}
    multiple     → список id                         {"13": [46, 48]}
    ordering     → список id в выбранном порядке     {"14": [52, 50, 51, 49]}
    fill_blanks  → {номер пропуска: id слова}        {"15": {"1": 60, "2": 58}}

Баллы: single — всё или ничего; multiple — (верные − лишние) / все верные, не меньше 0;
ordering — доля позиций на своих местах; fill_blanks — доля верно заполненных пропусков.
"""
from academy.models import Question, QuestionType, Quiz


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(value) -> list[int]:
    if not isinstance(value, list):
        return []
    return [i for i in (_as_int(v) for v in value) if i is not None]


def correct_answer(q: Question):
    """Правильный ответ в том же формате, что и ответ пользователя."""
    options = list(q.options.all())
    if q.type == QuestionType.SINGLE:
        return next((o.id for o in options if o.is_correct), None)
    if q.type == QuestionType.MULTIPLE:
        return sorted(o.id for o in options if o.is_correct)
    if q.type == QuestionType.ORDERING:
        return [o.id for o in sorted(options, key=lambda o: o.correct_position or 0)]
    return {str(o.correct_position): o.id for o in options if o.correct_position}


def grade_question(q: Question, answer) -> float:
    """Доля от 0 до 1."""
    options = list(q.options.all())
    valid_ids = {o.id for o in options}

    if q.type == QuestionType.SINGLE:
        chosen = _as_int(answer)
        return 1.0 if chosen in {o.id for o in options if o.is_correct} else 0.0

    if q.type == QuestionType.MULTIPLE:
        chosen = set(_int_list(answer)) & valid_ids
        correct = {o.id for o in options if o.is_correct}
        if not correct:
            return 0.0
        return max(0.0, (len(chosen & correct) - len(chosen - correct)) / len(correct))

    if q.type == QuestionType.ORDERING:
        expected = correct_answer(q)
        given = _int_list(answer)
        if len(given) != len(expected) or set(given) != set(expected):
            return 0.0
        return sum(g == e for g, e in zip(given, expected)) / len(expected)

    if q.type == QuestionType.FILL_BLANKS:
        # на один пропуск может быть несколько допустимых слов (синонимы)
        allowed: dict[int, set[int]] = {}
        for o in options:
            if o.correct_position:
                allowed.setdefault(o.correct_position, set()).add(o.id)
        if not allowed:
            return 0.0
        given = answer if isinstance(answer, dict) else {}
        used: set[int] = set()
        hits = 0
        for blank, ids in allowed.items():
            chosen = _as_int(given.get(str(blank), given.get(blank)))
            if chosen in ids and chosen not in used:  # одно слово нельзя вставить дважды
                hits += 1
            if chosen is not None:
                used.add(chosen)
        return hits / len(allowed)

    return 0.0


def grade_quiz(quiz: Quiz, answers: dict) -> tuple[int, list[dict]]:
    """Возвращает (процент, детали по вопросам)."""
    answers = answers if isinstance(answers, dict) else {}
    earned = total = 0.0
    details = []
    for q in quiz.questions.prefetch_related("options"):
        fraction = grade_question(q, answers.get(str(q.id), answers.get(q.id)))
        earned += fraction * q.points
        total += q.points
        details.append({"question_id": q.id, "fraction": round(fraction, 2), "correct": fraction == 1.0})
    score = round(earned / total * 100) if total else 0
    return score, details
