# Изменения API для фронтенда

Сюда backend записывает каждое изменение API (`/api/v1`). Правило: существующие поля и адреса не переименовываются и не удаляются — только добавляются. Если правка всё-таки ломает совместимость, она отмечена **⚠ несовместимо**.

Актуальная схема всегда в Swagger: http://localhost:8080/api/docs/

---

## Руководитель в отпуске или уволен: И.О. и эскалация

Только добавления. Кто согласует шаг руководителя, считается заново при каждой проверке:
1. руководитель автора на месте → он;
2. руководитель в утверждённом отпуске или уволен, но назначил И.О. на эти даты → И.О.;
3. иначе → вышестоящий руководитель, и для него те же правила (до CEO);
4. никого нет на месте по всей цепочке → общий пул HR (любой HR, кроме автора).

И.О. не согласует собственные заявки (тогда заявка уходит вышестоящему). Если заявка уже ждала руководителя, а он ушёл в отпуск, его уволили или он назначил/отменил И.О., согласующий меняется сам (worker пересчитывает раз в минуту, а также сразу после утверждения отпуска, изменения замещения, синхронизации с 1С:ЗУП). В истории заявки появляется событие «Согласующий изменён…» (`from_status == to_status`, `actor_name = null`), новый согласующий и автор получают уведомления.

### Заявки

- `GET /requests/{id}` (и ответы на действия) — новое поле `approver`, пока заявка в `waiting_manager_approval` (иначе `null`):
  `{kind: "manager" | "deputy" | "escalated" | "hr_pool", employee: {id, full_name} | null, acting_for: {id, full_name} | null, note}`. `employee = null` — согласует пул HR; `acting_for` — за кого действует И.О.; `note` — готовый текст («Согласует И.О. … за … (… — в отпуске)»).
- `GET /requests?scope=approvals` и счётчик на главной учитывают маршрут: заявка видна И.О. и вышестоящему руководителю, а руководителю в отпуске — нет. Заявки, по которым пользователь уже принимал решение, остаются ему доступны по прямой ссылке.
- `allowed_actions` тоже по маршруту: у руководителя в отпуске кнопок нет.

### Замещение (И.О.)

| Метод | Адрес | Что делает |
|---|---|---|
| GET | `/me/delegations` | `{can_delegate, candidates[], delegations[], acting_for[]}`: можно ли назначать (есть подчинённые), кого можно (`{id, full_name, position}` — прямые подчинённые и коллеги из своего подразделения с учётной записью), мои замещения за последние 30 дней и будущие, за кого я сейчас И.О. |
| POST | `/me/delegations` | `{deputy_id, date_from, date_to}` → `201` замещение. Ошибки `400`: И.О. не из команды/подразделения, дата в прошлом, конец раньше начала, больше 92 дней, пересечение с другим замещением; `403` — у пользователя нет подчинённых |
| POST | `/me/delegations/{id}/revoke` | отменить своё замещение |

Замещение: `{id, manager, deputy, date_from, date_to, revoked_at, state}`, `state`: `planned` | `active` | `finished` | `revoked`. Замещение срабатывает, только пока руководителя нет на месте; назначить его можно заранее.

- `GET /me` → `permissions`: у сотрудника, который сейчас И.О., появляется `requests.approve` (пункт меню «Согласование»).
- HR может назначить И.О. за руководителя в Django Admin («Замещения руководителей»), дату увольнения сотрудника — в карточке сотрудника. Из 1С:ЗУП приходит поле `dismissed_on`.

### Что поменялось во фронтенде
- `src/components/DelegationCard.tsx` — блок «Замещение (И.О.)» в профиле и плашка «Вы исполняете обязанности…» (профиль и главная).
- `RequestDetailPage.tsx` — строка «Согласует: … (И.О. за … / вышестоящий руководитель / HR)».

---

## Дизайн экранов: вакансии, обзор HR, статус для кандидата, иконки курсов

Только добавления, старые поля и адреса работают как раньше.

### Вакансии (HR)

| Метод | Адрес | Что делает |
|---|---|---|
| GET | `/recruitment/vacancies?status=&q=` | как раньше + новые поля: `status` (`draft` \| `active` \| `closed`), `department {id, name}`, `employment_type` (`full_time` \| `part_time` \| `contract` \| `internship`), `salary_from`, `salary_to`, `description`, `active_candidates_count`, `created_at`. `is_open` остался (= `status == "active"`) |
| POST | `/recruitment/vacancies` | создать: `title_ru*`, `title_kk`, `department_id`, `hiring_manager_id` (id **сотрудника**), `employment_type`, `description`, `salary_from`, `salary_to`, `status` (по умолчанию `active`). Ответ `201` — вакансия в формате списка |
| PATCH | `/recruitment/vacancies/{id}` | изменить любые поля из POST, например `{status: "closed"}` |
| GET | `/recruitment/departments` | `[{id, name}]` для формы |

- В публичной форме (`/careers/vacancies`) видны только `active`; на `draft` и `closed` резюме не принимаются.
- `GET /recruitment/interviewers` — новое поле `employee_id` (для выбора руководителя вакансии).

### Кандидаты

- Список и карточка: новые поля `number` (`CV-0018`) и `match_score` (0–100).
- Карточка: `match {score, factors[{key, points, max}]}` — `key`: `salary`, `resume`, `letter`, `progress`, `interviews`; сумма `max` = 100. Это **балл по правилам, не AI** (зарплата в вилке, PDF/ссылка, сопроводительный комментарий, этап, отзывы интервьюеров). AI-оценку позже добавит AI Jana.
- Карточка: `vacancy_status` — статус вакансии кандидата.
- `steps[]` — новое поле `date`: когда шаг пройден (скрининг — просмотр резюме, интервью — их дата, решение — дата найма/отказа), `null`, если ещё нет.
- `POST /recruitment/candidates/{id}/actions` — для `hire` можно передать `close_vacancy: true`, вакансия станет `closed`.

### Дашборд HR и календарь

- `GET /recruitment/summary` — новые поля: `upcoming_count` (всем); только HR: `open_vacancies`, `active_candidates`, `pending_requests` (заявки сотрудников в статусе «В обработке HR», кроме своих), `top_candidates[]` (5 лучших по `match_score`, формат списка кандидатов).
- `GET /recruitment/interviews?from=YYYY-MM-DD&days=31` — интервью за период (по умолчанию с сегодня на 31 день, максимум 92), без отменённых. HR — все, руководитель — свои, сотрудник — `403`. Формат — как `upcoming_interviews`.

### Кандидат смотрит статус (публично, без входа)

- `POST /careers/applications` теперь отвечает `{"status": "ok", "number": "CV-0018"}` — номер показать кандидату.
- `POST /careers/status` `{number, email}` → `{number, full_name, vacancy, stage, created_at, steps[{key, state, date}], next_interview {kind, scheduled_at, location} | null}`. Не совпали номер и почта — `404`. Не больше 20 запросов в час с IP → `429`. Отзывов, комментариев и имён HR в ответе нет.

### Вход

- `POST /auth/login` — в поле `username` можно передать рабочую почту сотрудника (например `…@demo.janapost.test`), формат запроса не изменился.

### Jana Academy

- Курс (`CourseShort`, каталог, назначения): новое поле `cover_icon` — ключ иконки из набора (`training`, `policies`, `onboarding`, `performance`, `company`, `people`, `documents`, `certificate`). Во фронтенде: `courseIcon(key)` в `src/components/icons.ts`. Поле `cover_emoji` осталось, но больше не используется.

---

## Подбор персонала (рекрутинг)

Только новые адреса, старые не менялись. Права: HR (`hr_admin`) — всё; руководитель — только кандидаты, у которых он интервьюер (только просмотр и отзыв); сотрудник — `403`. В `GET /me` → `permissions` появились `recruitment.manage` (HR) и `recruitment.interviews` (HR и руководители).

### Публичные (без входа) — форма на странице входа

| Метод | Адрес | Что делает |
|---|---|---|
| GET | `/careers/vacancies` | открытые вакансии: `id, title_ru, title_kk, department, description` |
| POST | `/careers/applications` | отправить резюме, **multipart/form-data**: `vacancy_id*`, `full_name*`, `email*`, `phone*`, `social`, `profile_url`, `resume_pdf` (PDF до 10 МБ), `expected_salary`, `comment`, `consent*` (`true`), `website` (скрытое поле-ловушка, всегда пустое). Нужна ссылка `profile_url` **или** файл. Ответ `201 {"status":"ok"}`; не больше 5 отправок в час с IP → `429` |

### Раздел «Подбор»

| Метод | Адрес | Что делает |
|---|---|---|
| GET | `/recruitment/summary` | `{new_resumes, by_stage, upcoming_interviews[]}` — для дашборда; у руководителя только `upcoming_interviews` (свои) |
| GET | `/recruitment/candidates?vacancy=&stage=&q=` | список: `id, full_name, vacancy, stage, reviewed, expected_salary, created_at, next_interview` |
| GET | `/recruitment/candidates/{id}` | карточка: контакты, `resume_url`, `comment`, `steps[] {key, label, state}`, `allowed_actions[]`, `interviews[]`, `events[]` |
| POST | `/recruitment/candidates/{id}/actions` | `{action: review \| next \| reject \| hire, comment}` — «Ознакомлен», «Следующий этап», «Отклонить», «Нанять» |
| POST | `/recruitment/candidates/{id}/interviews` | назначить / перенести интервью текущего этапа: `{scheduled_at (ISO), duration_min, interviewer_id?, location}` |
| GET | `/recruitment/candidates/{id}/resume` | PDF (только HR и интервьюер кандидата; можно показывать в `<iframe>` на сайте) |
| GET | `/recruitment/vacancies` | вакансии с `candidates_count` — для фильтра (HR) |
| GET | `/recruitment/interviewers` | кого можно назначить интервьюером: `id, full_name, role` (HR) |
| POST | `/recruitment/interviews/{id}/feedback` | `{feedback}` — отзыв интервьюера, интервью становится `done` |

- **Этапы** (`stage`): `screening` → `hr_interview` → `tech_interview` → `hired` / `rejected`. `decision_stage` — на каком этапе принят найм или отказ.
- **Шаги** (`steps[].state`): `done` (галочка), `current`, `pending` (серый), `rejected`, `skipped`; последний шаг `decision` — `hired` / `rejected` / `pending`. Скрининг получает `done` после «Ознакомлен», отказа или перехода на интервью.
- **Кнопки** рисуйте по `allowed_actions`: `review`, `next`, `reject`, `hire`, `schedule` (показать форму интервью). У руководителя список пустой — решения принимает HR.
- **PDF не лежит в `/media`**: его отдаёт только `resume_url` после проверки прав.
- **Новый тип уведомления** `recruitment`: «Новое резюме…» (HR), «Техническое интервью: …» (интервьюеру), «Принят кандидат…» (руководителю вакансии). Ссылка — `/recruitment/{id}`.

---

## Live-уведомления (SSE)

Добавление, старые адреса не изменились.

### Новый адрес: `GET /notifications/stream`

Поток Server-Sent Events. Пользователь — из сессии (cookie), каждый получает только свои уведомления; без входа — `403`.

```
retry: 5000

event: ready
data: {"unread": 3}

event: notification
data: {"id": 201, "type": "request_status_changed", "title": "…", "body": "…", "link": "/requests/101",
       "is_read": false, "created_at": "2026-10-17T17:59:44+05:00", "unread": 4}

: ping
```

- `ready` — сразу после подключения, `unread` = число непрочитанных.
- `notification` — новое уведомление: те же поля, что в `GET /notifications`, плюс `unread`.
- `: ping` — комментарий каждые 20 с, чтобы соединение не закрылось; обрабатывать не нужно.
- Обрыв связи браузер переподключает сам через 5 с (`retry`).

Подписка в браузере (уже сделана в `src/api/live.ts`, используется в `Layout.tsx`):

```ts
const source = new EventSource("/api/v1/notifications/stream");
source.addEventListener("notification", (e) => { /* JSON.parse(e.data) */ });
```

### Что поменялось во фронтенде

- `src/api/live.ts` — хук `useLiveNotifications(onNotification)`, возвращает `true`, пока поток подключён.
- `Layout.tsx` — на событие перечитывается счётчик уведомлений (а следом заявки, главная и список уведомлений, как раньше). Опрос `unread-count` остался запасным: раз в 60 с, пока поток работает, и раз в 10 с, если потока нет.

---

## Этап 4. Интеграции 1С:ЗУП и Documentolog

Все изменения — добавления, текущий фронтенд работает без правок.

### Новые поля в карточке заявки

`GET /requests/{id}`, а также ответы `POST /requests` и `PATCH /requests/{id}/approve-manager | approve-hr | reject | cancel | submit`:

| Поле | Тип | Значения |
|---|---|---|
| `doc_status` | string | `""` — приказа ещё нет, `on_signing` — на подписи в Documentolog, `signed` — подписан, `rejected` — отклонён |
| `doc_registration_number` | string | рег. № подписанного приказа, например `15-к/2026`; пусто, пока не подписан |

Поля `external_doc_id` (id приказа в Documentolog) и `external_zup_id` (№ документа «Отпуск» в 1С:ЗУП) были и раньше, теперь они заполняются.

### Поведение, которое стоит учесть в интерфейсе

- **Статус заявки не меняется.** После утверждения заявка остаётся `approved_sent_to_1c`; о внешних системах говорят поля выше и история.
- **Новые события в истории** (`events[]`) после утверждения: у них `from_status == to_status == "approved_sent_to_1c"`, `actor_name = null` (система), текст в `comment`:
  - «Передаётся в: 1С / бухгалтерия, 1С:ЗУП, Documentolog» — в событии утверждения;
  - «1С / бухгалтерия: документ № BUH-…», «1С:ЗУП: документ «Отпуск» № …», «Documentolog: приказ отправлен на подпись (№ DL-…)»;
  - примерно через 10 с — «Documentolog: приказ подписан, рег. № …» или «Documentolog: приказ отклонён — …».
- **Номера документов могут появиться не сразу.** Обычно они уже в ответе на `approve-hr`. Если внешняя система была недоступна, их досылает worker (через 30 с, 1, 2, 4… мин), и они появятся позже — данные обновятся через существующий опрос уведомлений.
- **Новые уведомления** (тип прежний — `request_status_changed`): «Заявка ZR-…: приказ подписан», «Заявка ZR-…: приказ отклонён в Documentolog» (сотруднику и HR).
- **Профиль** (`GET /me/profile`, `/team/{id}`): данные теперь обновляются синхронизацией с 1С:ЗУП; поле `source` = `"zup"`. Формат не изменился.

### Новый адрес (не для фронтенда)

`POST /integrations/documentolog/webhook` — вызывает только Documentolog (проверка HMAC-подписи `X-Documentolog-Signature`). Фронтенду его вызывать не нужно.
