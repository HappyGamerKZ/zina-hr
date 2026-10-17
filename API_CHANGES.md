# Изменения API для фронтенда

Сюда backend записывает каждое изменение API (`/api/v1`). Правило: существующие поля и адреса не переименовываются и не удаляются — только добавляются. Если правка всё-таки ломает совместимость, она отмечена **⚠ несовместимо**.

Актуальная схема всегда в Swagger: http://localhost:8080/api/docs/

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
