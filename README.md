# JanaМен — единая HR-платформа (Jana Post × Terricon Valley, Challenge 02)

Прототип: вход и роли → личный кабинет → заявки на отпуск / аванс → согласование → уведомления. Дальше — Jana Academy и AI Jana.

- Требования кейса: [SPEC.md](SPEC.md)
- Архитектура, схема БД, места интеграции 1С:ЗУП и Documentolog: [ARCHITECTURE.md](ARCHITECTURE.md)

## Запуск

Нужен Docker Desktop.

```bash
docker compose up --build
```

| Что | Адрес |
|---|---|
| Приложение | http://localhost:8080 |
| Swagger (API) | http://localhost:8080/api/docs/ |
| Django Admin (HR-контент) | http://localhost:8080/admin/ (логин `hr`) |

При первом старте backend создаёт миграции, применяет их и заполняет демо-данные. Миграции появятся в `backend/*/migrations/`, их нужно закоммитить.

Сбросить демо-данные:

```bash
docker compose exec backend python manage.py seed --reset
```

### Без Docker (для разработки)

```bash
cd backend && pip install -r requirements.txt && python manage.py makemigrations org accounts hr_requests notifications integrations && python manage.py migrate && python manage.py seed && python manage.py runserver
```

```bash
cd frontend && npm install && npm run dev
```

Без `POSTGRES_HOST` backend использует SQLite. Фронт на http://localhost:5173 проксирует `/api` на `:8000`.

## Тестовые логины

Пароль у всех: `demo1234` (только для демо, реальных данных нет).

| Логин | Роль | Кто |
|---|---|---|
| `employee` | сотрудник | Сапарова Айгерим, специалист по логистике |
| `manager` | руководитель | Бекенов Ерлан, руководитель отдела логистики (3 подчинённых) |
| `hr` | HR | Нурланова Асель, HR-специалист; руководитель — `hr_head` (есть доступ в Django Admin) |
| `hr_head` | HR | Касымова Динара, директор по персоналу (Head of HR); руководителя нет |
| `employee2` | сотрудник | Жумабаев Арман, отдел продаж — `manager` его не видит |
| `sales_head` | руководитель | Ахметова Сауле, руководитель отдела продаж |

## Демо-сценарии

1. **Вход и кабинет.** `employee` → главная: профиль, остаток отпуска, быстрые сервисы, последние заявки, уведомления.
2. **Заявка и адаптивный маршрут согласования** (отпуск и аванс):
   - **Сотрудник:** `employee` создаёт отпуск (например, 3–14 ноября) → «На согласовании у руководителя». `manager` → «Согласование» → «Одобрить» → «В обработке HR». `hr` → «Оформить приказ» → «Утверждено / Передано в 1С» с № документа. У `employee` уведомления и вся история в карточке.
   - **HR-специалист:** у `hr` уже есть аванс на согласовании. `hr_head` → «Одобрить» → сразу «Утверждено / Передано в 1С»: шаг HR пропускается, HR не оформляет приказ сам себе.
   - **Head of HR:** `hr_head` создаёт заявку → она сразу «Утверждено / Передано в 1С», потому что руководителя нет.
3. **Ролевой доступ.** `manager` видит в «Команде» только своих трёх подчинённых. Заявка `employee2` ему не видна: прямой запрос `GET /api/v1/requests/<id>` или `/api/v1/team/<id>` возвращает **404**. Права проверяет сервер (`backend/org/scopes.py`), а не интерфейс.
4. Jana Academy — следующий этап.
5. и 6. AI Jana — следующий этап.

## Что реализовано

| Часть | Статус |
|---|---|
| Вход (Django-сессия + CSRF), 3 роли, серверная проверка прав, 404 на чужие данные | ✅ полностью |
| Профиль из «1С:ЗУП» (read-only), остаток отпуска с учётом заявок | ✅ полностью; данные — seed вместо mock-сервиса ЗУП |
| Заявки «Отпуск» и «Аванс»: адаптивный маршрут (руководитель → HR → 1С, с учётом `manager_id` и роли автора), отклонение, отмена, история | ✅ полностью, покрыто тестами (`python manage.py test hr_requests`) |
| Мои заявки, заявки команды, очередь согласования | ✅ полностью |
| Уведомления: новая заявка, смена статуса (polling 15 с) | ✅ полностью; SSE, email — будущее |
| RU / KZ | ✅ интерфейс; контент из БД — частично (`name_kk`) |
| Django Admin для HR | ✅ |
| Jana Academy (LMS) | ⏳ следующий этап (см. ARCHITECTURE.md §6) |
| AI Jana (RAG по базе знаний) | ⏳ следующий этап (§8) |
| Передача в бухгалтерию после утверждения HR | 🧩 mock: `integrations/adapters.py` (`MockAccountingAdapter`), журнал в Django Admin; боевой адаптер — через `ACCOUNTING_PROVIDER` |
| Интеграция 1С:ЗУП | 🧩 mock: следующий этап — контейнер `mock-1c-zup` + адаптер `HRISProvider` (§7) |
| Интеграция Documentolog | 🧩 mock: следующий этап — контейнер `mock-documentolog` + webhook → статус `registered` (§7) |
| Рекрутинг, ЭЦП, мобильное приложение | вне рамок кейса |

## Структура

```
backend/    Django + DRF: accounts, org, hr_requests, notifications, core (события, права, seed)
frontend/   React + TypeScript + Vite, nginx (SPA + прокси /api и /admin)
```
