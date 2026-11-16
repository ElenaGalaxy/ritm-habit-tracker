# Ритм — трекер привычек + AI-ассистент (MVP)

Однопользовательский веб-трекер привычек: отметки в один тап, серии, заморозки,
календарь, статистика, бережные напоминания в Telegram и AI-помощник, который
предлагает привычки под цель и делает недельный обзор.

Интерфейс — адаптивный SPA на нативном JavaScript (без сборки и Node.js),
сервер — Flask + SQLite, PDF-отчёты — ReportLab. Всё работает локально, ключи
AI и Telegram остаются на сервере.

---

## Быстрый старт

Требования: **Python 3.11+** (проверено на 3.12). Node.js и npm не нужны.

```bash
# 1. Виртуальное окружение
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 2. Зависимости
pip install -r requirements.txt

# 3. Запуск (демо-данные создаются автоматически)
python app.py
```

Откройте <http://127.0.0.1:5000>. Сервер слушает `127.0.0.1:5000` и запускает
планировщик напоминаний в фоновом потоке.

### Windows: запуск в один клик

Дважды щёлкните `start.bat` в папке проекта. Скрипт запустит сервер из `.venv`
и откроет <http://127.0.0.1:5000> в браузере. Остановить сервер — `Ctrl+C`
в открывшемся окне командной строки.

### Демо-доступ

| Роль  | Email               | Пароль      |
|-------|---------------------|-------------|
| Демо  | `demo@treker.local` | `demo1234`  |
| Админ | `admin@treker.local`| `admin1234` |

В демо-кабинете уже есть 5 привычек и история за 75 дней. Кнопка
«Открыть демо-кабинет» на экране входа делает то же самое.

Чтобы создать чистую базу, удалите `instance/tracker.db` и перезапустите
сервер. Демо-данные создаются только если в базе ещё нет пользователей.

> Для публичного деплоя отключите демо-доступ (`ALLOW_DEMO_LOGIN=false`,
> `SEED_DEMO=false`), удалите демо-базу и задайте собственный `SECRET_KEY`.

### Деплой на Render (демо)

В репозитории есть `render.yaml` для бесплатного демо-стенда:

1. В [Render Dashboard](https://dashboard.render.com) выберите
   **New → Blueprint** и подключите GitHub-репозиторий
   `ElenaGalaxy/ritm-habit-tracker`.
2. Render создаст web service `ritm-habit-tracker` на Python 3.12,
   установит зависимости и запустит `gunicorn ... wsgi:app`.
3. После деплоя откройте выданный `onrender.com`-URL и войдите в демо-кабинет.

Free-план использует эфемерную файловую систему: база SQLite сбрасывается
при рестарте и каждом деплое, а сам сервис засыпает после простоя — в это
время планировщик напоминаний не работает. Это нормально для демо, но не
для реальных данных.

Для постоянного хранения перейдите на платный план, добавьте persistent disk
с mount path `/var/data` и задайте:

```text
DATABASE_PATH=/var/data/tracker.db
ALLOW_DEMO_LOGIN=false
SEED_DEMO=false
SESSION_COOKIE_SECURE=true
```

Telegram и AI подключаются через Environment Variables в Render:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET`,
`AI_API_KEY`. После деплоя зарегистрируйте вебхук:

```text
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<service>.onrender.com/telegram/webhook/<SECRET>
```

---

## Переменные окружения

Скопируйте `.env.example` в `.env` — сервер читает его при старте. Все
переменные необязательны: без них приложение работает в демо-режиме.

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `SECRET_KEY` | случайный при старте | Подпись cookie. Задайте постоянный в продакшене. |
| `DATABASE_PATH` | `instance/tracker.db` | Путь к файлу SQLite. |
| `ALLOW_DEMO_LOGIN` | `true` | Разрешить вход в демо-кабинет. |
| `SEED_DEMO` | `true` | Создавать демо-данные при пустой базе. |
| `DOCS_PUBLIC` | `true` | Документация доступна без входа. |
| `SCHEDULER_ENABLED` | `true` | Фоновые напоминания каждую минуту. |
| `SESSION_COOKIE_SECURE` | `false` | Включайте при HTTPS. |
| `TELEGRAM_BOT_TOKEN` | — | Токен бота от @BotFather. |
| `TELEGRAM_BOT_USERNAME` | — | Username бота без `@`. |
| `TELEGRAM_WEBHOOK_SECRET` | — | Секрет в URL вебхука. |
| `AI_API_KEY` | — | Ключ OpenAI-совместимого провайдера. |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Базовый URL API. |
| `AI_MODEL` | `gpt-4o-mini` | Модель для генерации. |
| `AI_TIMEOUT` | `40` | Таймаут запроса к AI, секунды. |

---

## Что умеет приложение

### Привычки

- Три типа: `boolean` (да/нет), `quantity` (количество), `duration` (минуты).
- Расписания: `daily`, `weekdays` (пн–пт), `times_per_week` (N раз в неделю).
- До **30 активных** привычек; архив, пауза, завершение и восстановление.
- Иконка, цвет, цель, единица измерения, время напоминания, лимит заморозок.
- Создание из шаблонов, вручную или из AI-плана (пакетно, 3–5 штук).

### Отметки

- Boolean — один тап. Quantity/duration — степпер или слайдер.
- Оптимистичное обновление интерфейса с откатом при ошибке.
- Удаление привычки с Undo в течение **10 секунд**.
- Редактирование прошедших дней с пересчётом серий и статистики.
- Статусы дня: `done`, `partial`, `skipped`, `frozen`, `missed`, `empty`.

### Серии и заморозки

- `done` увеличивает серию, `partial` сохраняет, но не увеличивает,
  `skipped`/`missed` обнуляют.
- `frozen` («Пауза») сохраняет серию и засчитывается в недельную квоту.
- Не более **2 заморозок в календарный месяц** на привычку (настраивается 0–5).
- Для `times_per_week` серия считается по неделям (пн–вс): неделя успешна,
  если набрана квота N.
- Незаполненный сегодняшний день не обнуляет текущую серию.

### Календарь и статистика

- Месячный календарь со статусами и точками по привычкам.
- Годовая тепловая карта; клик по дню открывает редактор.
- Периоды статистики: 7 / 30 / 90 / 365 дней.
- Карточки: текущая и лучшая серия, процент недели и месяца, свободные заморозки.
- График по дням, разбивка по привычкам, лучший день недели.

### Условия-события

Событие создаётся один раз и логируется в `condition_events`:

1. **Серия ≥ 7** — мягкое поздравление.
2. **2 пропуска подряд** — предложение паузы, а не упрёк.
3. **Недельное выполнение < 50%** — предложение уменьшить цель.

События можно отключить в настройках. Пропуски отображаются серым, не красным;
формулировки — «Пауза», «Вернёмся завтра».

### Напоминания

- Telegram-бот, тихие часы, snooze на 1 час, не чаще одного раза в день.
- Если привычка уже отмечена — напоминание не отправляется.
- Без токена бота напоминания сохраняются в журнале со статусом `simulated`.
- Подключение: `POST /telegram/connect` → код → `/start <код>` в боте,
  либо демо-подключение `POST /telegram/simulate-connect`.

### AI-ассистент

- Генерация **3–5 привычек** под цель и недельный обзор.
- Строгая серверная JSON-валидация; при невалидном ответе — безопасный fallback.
- Превью и применение только после подтверждения пользователя.
- Отдельное согласие на отправку обезличенных данных (`ai_consent`).
- Лимит **10 запросов в день**; история запросов хранится в `ai_requests`.
- Без `AI_API_KEY` сервер отдаёт локальный шаблонный план с `fallback: true`.
- Никаких медицинских советов и токсичной мотивации.

### Экспорт и документы

- `GET /export.csv`, `GET /export.json`, `GET /export/report.pdf`.
- `GET /docs/tz.md`, `GET /docs/tz.pdf` — ТЗ.
- `GET /docs/file/schema.sql`, `/docs/file/seed.json`, `/docs/file/README.md`.
- `GET /openapi.yaml` — спецификация API.

---

## API

Все ответы — JSON (кроме экспорта и документов). Аутентификация — cookie
`ht_session` (HttpOnly, SameSite=Lax). Изменяющие запросы проверяют `Origin`.

Основные эндпоинты:

```
POST   /auth/register | /auth/login | /auth/demo | /auth/logout
GET    /auth/me
POST   /auth/onboarding

GET    /today
GET    /habits            POST /habits
GET    /habits/<id>       PATCH /habits/<id>       DELETE /habits/<id>
POST   /habits/batch
POST   /habits/<id>/restore
GET    /templates

GET    /logs              POST /logs               DELETE /logs
POST   /logs/freeze       DELETE /logs/freeze
GET    /calendar          GET /calendar/day
GET    /events            POST /events/seen
GET    /conditions        PATCH /conditions

GET    /stats             GET /stats/heatmap       GET /stats/habit/<id>

GET    /ai/status         POST /ai/generate        POST /ai/review
GET    /ai/history

PATCH  /settings
POST   /telegram/connect | /telegram/simulate-connect | /telegram/disconnect
POST   /telegram/webhook/<secret>
GET    /reminders         POST /reminders/snooze   POST /reminders/tick (admin)
DELETE /account

GET    /export.csv | /export.json | /export/report.pdf
GET    /docs/tz.md | /docs/tz.pdf | /docs/file/<name> | /openapi.yaml
GET    /admin/overview    GET /admin/errors
PATCH  /admin/templates/<id>
GET    /health
```

Полные схемы запросов и ответов — в [`openapi.yaml`](openapi.yaml).

### Пример: вход и отметка

```bash
curl -c cookies.txt -X POST http://127.0.0.1:5000/auth/demo
curl -b cookies.txt http://127.0.0.1:5000/today
curl -b cookies.txt -X POST http://127.0.0.1:5000/logs \
  -H "Content-Type: application/json" \
  -d '{"habit_id":1,"date":"2026-11-13","value":1,"status":"done"}'
```

---

## Тесты

```bash
python -m unittest discover -s tests -v
```

Покрыты:

- серии `daily`/`weekdays`, влияние `partial`, `frozen`, `skipped`;
- недельная логика `times_per_week`;
- лимит заморозок в календарный месяц;
- авторизация, права, CSRF, лимит активных привычек;
- создание/редактирование/удаление привычек и отметок;
- календарь, статистика, AI fallback и согласие;
- экспорт CSV/JSON/PDF, документы и OpenAPI.

Тесты используют временную базу и не трогают `instance/tracker.db`.

---

## Структура проекта

```
app.py                     локальная точка входа + планировщик
wsgi.py                    production-вход для Gunicorn + планировщик
render.yaml                Blueprint для демо-стенда Render
.python-version            версия Python для Render
schema.sql                 схема SQLite
seed.json                  демо-данные (артефакт)
openapi.yaml               OpenAPI 3.0
requirements.txt           зависимости Python
tracker/
  __init__.py              фабрика приложения, ошибки, заголовки
  security.py              пароли, сессии, роли, rate-limit, CSRF
  stats.py                 серии, заморозки, выполнение, heatmap
  validation.py            валидация привычек, отметок и AI-ответов
  ai.py                    провайдер, fallback, промпты
  conditions.py            события-условия
  notifications.py         Telegram, тихие часы, snooze, tick
  exports.py               CSV/JSON
  pdf.py                   PDF-отчёт
  markdown_pdf.py          Markdown → PDF для ТЗ
  seed.py                  демо-пользователи и история
  db.py, utils.py, api_helpers.py
  routes/                  blueprints API
docs/
  TZ_habit_tracker_MVP.md  исходное ТЗ
static/
  css/app.css              дизайн-система, светлая/тёмная темы
  fonts/                   Playfair Display (OFL), локальный серифный шрифт
  img/sprig.svg            ботаническая линия для акцентов
  js/app.js                оболочка и hash-роутер
  js/views/                экраны приложения
  js/*.js                  API-клиент, UI-компоненты, утилиты
templates/index.html       единственная HTML-страница
tests/                     unittest
```

---

## Безопасность

- Пароли — PBKDF2-SHA256, 260 000 итераций, случайная соль.
- Токен сессии хранится в базе только как SHA-256 хэш; cookie HttpOnly.
- Проверка `Origin`/`Referer` для POST/PATCH/DELETE (SameSite=Lax).
- Роли проверяются на сервере: админ-раздел и `/reminders/tick` — только admin.
- CSP без inline-скриптов, `X-Frame-Options: DENY`, `nosniff`.
- AI- и Telegram-ключи читаются только из окружения сервера.
- Все пользовательские строки экранируются перед вставкой в HTML.
- SQL — только параметризованные запросы.
- Удаление аккаунта — каскадное, с подтверждением словом «УДАЛИТЬ».

---

## Ограничения MVP

- Один личный кабинет; мультипользовательский режим не является целью.
- Нет push-уведомлений в браузере и мобильного приложения.
- Напоминания без токена бота — только журнал (`simulated`).
- AI-провайдер должен быть OpenAI-совместимым.
- SQLite подходит для одного экземпляра приложения; для горизонтального
  масштабирования потребуется внешняя БД.
- Приложение не даёт медицинских рекомендаций и не заменяет специалиста.

---

## Лицензия

Учебный MVP. Используйте и адаптируйте свободно.
