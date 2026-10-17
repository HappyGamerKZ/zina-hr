import os
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080,http://localhost:5173"
)

INSTALLED_APPS = [
    "unfold",  # тема Django Admin — должна стоять до django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "core",
    "org",
    "accounts",
    "hr_requests",
    "notifications",
    "integrations",
    "academy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL в docker compose; без POSTGRES_HOST — SQLite для быстрого локального запуска.
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "janamen"),
            "USER": os.environ.get("POSTGRES_USER", "janamen"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский"), ("kk", "Қазақша")]
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))

# Загруженные файлы (фото, видео, PDF в уроках Academy). В docker compose — общий том с nginx.
MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media"))
if len(sys.argv) > 1 and sys.argv[1] == "test":
    MEDIA_ROOT = tempfile.mkdtemp(prefix="janamen-test-media-")  # тесты не мусорят в общем томе

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Вход в Django Admin без ?next= ведёт в админку, а не на несуществующий /accounts/profile/
LOGIN_REDIRECT_URL = "/admin/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "JanaМен API",
    "DESCRIPTION": "Единая HR-платформа: профиль, заявки, обучение, AI Jana",
    "VERSION": "0.1.0",
}

# Лимит аванса (mock: в будущем приходит из 1С:ЗУП по окладу сотрудника)
ADVANCE_MAX_AMOUNT = 500_000

# Куда уходят утверждённые HR заявки. mock_accounting — заглушка (integrations/adapters.py).
ACCOUNTING_PROVIDER = os.environ.get("ACCOUNTING_PROVIDER", "mock_accounting")

# Тема Django Admin (django-unfold): меню по разделам HR-платформы
from django.urls import reverse_lazy  # noqa: E402


def _admin_link(title, icon, model):
    app, name = model.split(".")
    return {"title": title, "icon": icon, "link": reverse_lazy(f"admin:{app}_{name}_changelist")}


UNFOLD = {
    "SITE_TITLE": "JanaМен",
    "SITE_HEADER": "JanaМен — администрирование",
    "SITE_SYMBOL": "badge",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {"title": "Jana Academy", "items": [
                _admin_link("Курсы", "school", "academy.course"),
                _admin_link("Модули", "folder", "academy.coursemodule"),
                _admin_link("Уроки (конструктор)", "article", "academy.lesson"),
                _admin_link("Тесты", "quiz", "academy.quiz"),
                _admin_link("Вопросы", "help", "academy.question"),
                _admin_link("Назначения", "assignment_ind", "academy.courseassignment"),
                _admin_link("Попытки тестов", "fact_check", "academy.quizattempt"),
            ]},
            {"title": "Заявки", "items": [
                _admin_link("Заявки", "description", "hr_requests.hrrequest"),
                _admin_link("Передачи в 1С / бухгалтерию", "receipt_long", "integrations.accountingexport"),
                _admin_link("Уведомления", "notifications", "notifications.notification"),
            ]},
            {"title": "Люди и структура", "items": [
                _admin_link("Сотрудники", "badge", "org.employee"),
                _admin_link("Подразделения", "apartment", "org.department"),
                _admin_link("Должности", "work", "org.position"),
                _admin_link("Пользователи", "person", "accounts.user"),
            ]},
        ],
    },
}
