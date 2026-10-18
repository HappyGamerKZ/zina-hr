"""База знаний AI Jana: загрузка статей, фрагменты по разделам и поиск с учётом роли.

Статьи лежат в assistant/kb/articles/*.md (их ведёт аналитик). В начале файла метаданные
(id, title, roles, tags), ниже русский текст, под ним казахская версия после метки
`<!-- lang: kk ... -->`. Статья режется на фрагменты по заголовкам `##`; у каждого фрагмента
язык (ru / kk), роли и id статьи — его AI Jana показывает как источник.

Поиск лексический (без векторной базы): слова вопроса и фрагмента приводятся к основе
(первые 5 букв — грубо, но для русского и казахского работает), вес слова — idf.
Статьи, закрытые для роли пользователя, отбрасываются до поиска.
"""
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent / "kb" / "articles"
ALL_ROLES = ("employee", "manager", "hr")
KK_MARKER = re.compile(r"^<!--\s*lang:\s*kk.*?-->\s*$", re.M)
KK_LETTERS = set("әғқңөұүһі")
WORD = re.compile(r"[0-9a-zа-яёәғқңөұүһі]+", re.I)
STEM = 5

# служебные слова — не помогают найти статью
STOPWORDS = set("""
и в во на с со к ко по о об от до за из у не ни но а же ли бы что как где когда какой какая какие
каких сколько можно нужно ли мне меня мой моя мои моих мы вы я он она они это этот эта эти для при
есть быть будет был была если или то тоже чтобы ещё еще уже там тут здесь всё все очень надо
жана jana ai пожалуйста подскажите скажите расскажите хочу хотел хотела
және мен бен пен да де та те ма ме ба бе па пе ғой қалай қайда қашан қандай неше қанша бар жоқ
бұл осы сол мен сен ол біз сіз олар менің сенің оның біздің сіздің үшін туралы керек бола ма ме
""".split())

ROLE_BY_USER = {"employee": "employee", "manager": "manager", "hr_admin": "hr"}

# одно понятие разными словами (основы по 5 букв): вопрос «про академию» находит «Jana Academy»
SYNONYMS = {
    "акаде": ["acade"], "дмс": ["емс", "страх"], "больн": ["ауру"], "зарпл": ["оклад"], "отгул": ["отпус"],
    "выдат": ["выдан", "выдач"], "выдай": ["выдан", "выдач"],  # «выдать справку» ↔ статус «Выдано»
}
ROLE_BOOST = 1.3  # статьи только для руководителей / HR — выше для них: «как выдать справку» у HR — про обработку
K1, B = 1.2, 0.75  # параметры BM25


@dataclass
class Chunk:
    article_id: str
    title: str  # название статьи на языке фрагмента
    heading: str  # заголовок раздела
    text: str
    lang: str  # ru | kk
    roles: tuple[str, ...]
    stems: dict[str, int] = field(default_factory=dict)  # основа слова → сколько раз


@dataclass
class Article:
    id: str
    title_ru: str
    title_kk: str
    roles: tuple[str, ...]
    tags: list[str]
    chunks: list[Chunk]

    def title(self, lang: str) -> str:
        return self.title_kk if lang == "kk" and self.title_kk else self.title_ru


def stems(text: str) -> list[str]:
    return [w[:STEM] for w in (m.lower() for m in WORD.findall(text)) if w not in STOPWORDS and len(w) > 1]


def detect_lang(text: str) -> str:
    """Казахский — если есть буквы, которых нет в русском."""
    return "kk" if KK_LETTERS & set(text.lower()) else "ru"


def _front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    _, head, body = raw.split("---", 2)
    meta = {}
    for line in head.strip().splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        meta[key.strip()] = value
    return meta, body


def _sections(text: str, lang: str, article_id: str, title: str, roles, extra: str) -> list[Chunk]:
    """Фрагменты по `##`. Название статьи и теги добавляются к каждому — так фрагмент находится по теме."""
    chunks = []
    parts = re.split(r"^## +", text, flags=re.M)
    intro = re.sub(r"^# .*$", "", parts[0], flags=re.M).strip()
    if intro:
        parts[0] = "Кратко\n" + intro
    else:
        parts = parts[1:]
    for part in parts:
        heading, _, body = part.partition("\n")
        body = body.strip()
        if not body:
            continue
        chunk = Chunk(article_id, title, heading.strip(), body, lang, roles)
        for s in stems(f"{title} {title} {heading} {body} {extra}"):
            chunk.stems[s] = chunk.stems.get(s, 0) + 1
        chunks.append(chunk)
    return chunks


def parse_article(path: Path) -> Article:
    raw = path.read_text(encoding="utf-8")
    meta, body = _front_matter(raw)
    article_id = meta.get("id") or path.stem
    roles = tuple(meta.get("roles") or ALL_ROLES)
    tags = meta.get("tags") or []
    marker = KK_MARKER.search(body)
    ru_text, kk_text = (body[:marker.start()], body[marker.end():]) if marker else (body, "")
    first_heading = re.search(r"^# +(.+)$", ru_text, re.M)
    title_ru = meta.get("title") or (first_heading.group(1).strip() if first_heading else article_id)
    kk_heading = re.search(r"^# +(.+)$", kk_text, re.M)
    title_kk = kk_heading.group(1).strip() if kk_heading else ""
    keywords = re.search(r"^Кілт сөздер:(.+)$", kk_text, re.M)
    kk_extra = keywords.group(1) if keywords else ""
    kk_text = re.sub(r"^Кілт сөздер:.*$", "", kk_text, flags=re.M)

    chunks = _sections(ru_text, "ru", article_id, title_ru, roles, " ".join(tags))
    if kk_text.strip():
        chunks += _sections(kk_text, "kk", article_id, title_kk or title_ru, roles, kk_extra)
    return Article(article_id, title_ru, title_kk, roles, tags, chunks)


@lru_cache(maxsize=1)
def load(kb_dir: str = str(KB_DIR)) -> tuple[list[Article], dict[str, float], float]:
    """Статьи, idf основ слов и средняя длина фрагмента. Кэш на процесс: после правки статей перезапустите backend."""
    articles = [parse_article(p) for p in sorted(Path(kb_dir).glob("*.md"))]
    chunks = [c for a in articles for c in a.chunks]
    df: dict[str, int] = {}
    for c in chunks:
        for s in c.stems:
            df[s] = df.get(s, 0) + 1
    n = len(chunks) or 1
    idf = {s: math.log(1 + n / d) for s, d in df.items()}
    avg_len = sum(sum(c.stems.values()) for c in chunks) / n
    return articles, idf, avg_len


@dataclass
class Hit:
    chunk: Chunk
    score: float  # 0..1 — доля «веса» вопроса, найденная во фрагменте


def query_stems(question: str) -> set[str]:
    q = set(stems(question))
    for s in list(q):
        q.update(SYNONYMS.get(s, []))
    return q


def search(question: str, user_role: str, lang: str | None = None, top_k: int = 4) -> list[Hit]:
    """Лучшие фрагменты, доступные роли.

    Порядок — по BM25 (частота слова во фрагменте, его редкость, длина фрагмента), фрагменты на языке
    вопроса чуть выше. score — доля веса слов вопроса, найденных во фрагменте: по нему решается,
    есть ли в базе надёжный ответ (порог AI_MIN_SCORE).
    """
    articles, idf, avg_len = load()
    role = ROLE_BY_USER.get(user_role, user_role)
    lang = lang or detect_lang(question)
    q = query_stems(question)
    if not q:
        return []
    default_idf = max(idf.values(), default=1.0)
    total = sum(idf.get(s, default_idf) for s in set(stems(question))) or 1.0
    ranked = []
    for article in articles:
        if role not in article.roles:
            continue
        for chunk in article.chunks:
            found = [s for s in q if s in chunk.stems]
            if not found:
                continue
            length = sum(chunk.stems.values())
            bm25 = sum(
                idf.get(s, default_idf) * chunk.stems[s] * (K1 + 1)
                / (chunk.stems[s] + K1 * (1 - B + B * length / avg_len))
                for s in found
            )
            if chunk.lang == lang:
                bm25 *= 1.15
            if "employee" not in article.roles:
                bm25 *= ROLE_BOOST
            coverage = min(sum(idf.get(s, default_idf) for s in found) / total, 1.0)
            ranked.append((bm25, Hit(chunk, coverage)))
    ranked.sort(key=lambda x: x[0], reverse=True)
    hits = [h for _, h in ranked]
    # не больше двух фрагментов одной статьи — чтобы в контекст попали разные источники
    picked, per_article = [], {}
    for h in hits:
        if per_article.get(h.chunk.article_id, 0) >= 2:
            continue
        per_article[h.chunk.article_id] = per_article.get(h.chunk.article_id, 0) + 1
        picked.append(h)
        if len(picked) == top_k:
            break
    return picked


def article(article_id: str) -> Article | None:
    return next((a for a in load()[0] if a.id == article_id), None)


def is_hidden_for(article_id: str, user_role: str) -> bool:
    a = article(article_id)
    return a is not None and ROLE_BY_USER.get(user_role, user_role) not in a.roles
