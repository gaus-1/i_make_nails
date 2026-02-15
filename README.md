# i-make-nails

Telegram-бот и мини-приложение для записи клиентов к мастеру маникюра. Клиенты выбирают дату и время в мини-аппе, мастер ведёт расписание, клиентов и настройки в той же среде.

**Цель проекта** — убрать необходимость вести очередь в блокноте и разгрузить личные сообщения в Telegram: запись и переносы происходят в мини-аппе, без бесконечных «на какое число свободно?» в личку.

---

## Возможности

**Клиент:** запись на дату/время, просмотр своих записей (день/неделя/месяц), отмена и перенос.

**Мастер:** расписание дня/недели/месяца, список клиентов (имя, телефон, ссылка в Telegram), настройки (часы работы, слоты, таймзона), блокировки дат (отпуск, выходной).

---

## Стек

**Бэкенд:** Python 3.13, aiogram 3, aiohttp. БД: PostgreSQL (прод) или SQLite (локально), SQLAlchemy 2, Alembic. Конфиг: Pydantic / pydantic-settings.

**Фронт мини-аппа:** TypeScript, Vite, раздача статики из `static/` через aiohttp.

**Тесты:** pytest (unit, integration, load), Vitest, Playwright (E2E). Линт: Ruff, Vulture в CI; pre-commit — Ruff, ruff-format, TypeScript при изменениях во frontend, YAML, концы файлов, детекция ключей и больших файлов.

---

## Структура репозитория

```
├── .github/workflows/      CI (Ruff, Vulture, pytest, Vitest, сборка, attestation)
├── bot/                    Бот и API мини-аппа
│   ├── api/                HTTP API: deps, schemas, telegram_auth, miniapp/routes
│   ├── config/             Настройки из env
│   ├── database/           Движок и сессии БД
│   ├── handlers/           Обработчики Telegram
│   ├── models/             SQLAlchemy-модели
│   └── services/           Слоты, записи
├── frontend/
│   ├── e2e/                Playwright: client.spec, master.spec
│   ├── scripts/            start-e2e-server.mjs
│   └── src/                Рендер, API, стили, Vitest
├── scripts/                check-frontend-tsc.mjs (pre-commit)
├── alembic/                Миграции БД
├── tests/                  pytest: unit, integration, load
├── web_server.py           Точка входа: aiohttp, роуты, статика
├── Dockerfile              Сборка фронта, образ Python, static из dist
├── Procfile, railway.json  Деплой Railway
├── package.json            test, test:frontend, test:backend, test:all
└── .pre-commit-config.yaml
```

Каталог `static/` не коммитится: заполняется при сборке (копирование из `frontend/dist` в Dockerfile или при запуске E2E).

---

## Локальный запуск

Создать venv и установить зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

В `.env` или в окружении задать: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY`, `MASTER_TELEGRAM_IDS`, `ADMIN_TELEGRAM_IDS`, `WEBHOOK_DOMAIN`.

Для локальной разработки: `DATABASE_URL=sqlite:///local.db`, `MINIAPP_AUTH=dev` (запросы без initData, по заголовку/query `X-Telegram-Id`).

Запуск:

```bash
alembic upgrade head
python web_server.py
```

Порт по умолчанию 8000 (или `PORT`). Статика отдаётся из `static/`; если каталога нет — собрать фронт (ниже) или использовать Docker.

Сборка фронта:

```bash
cd frontend
npm install
npm run build
```

Содержимое `frontend/dist` скопировать в `static/` в корне (или собрать образ через Docker — тогда копирование в образе).

---

## Тесты

**Бэкенд (pytest):**

```bash
pytest
# или из корня:
npm run test:backend
```

**Фронт (Vitest):**

```bash
cd frontend && npm run test
# или из корня:
npm test
```

**Всё (Vitest + pytest):**

```bash
npm run test:all
```

**E2E (Playwright):** нужен свободный порт 8765.

```bash
cd frontend
npm run e2e
```

Скрипт собирает фронт, копирует в `static/`, поднимает сервер с `E2E_SERVER=1` и SQLite с сидом (один мастер, расписание на 7 дней). Если на Windows команда запуска сервера падает: вручную `node frontend/scripts/start-e2e-server.mjs`, затем `E2E_BASE_URL=http://localhost:8765 npm run e2e`.

---

## Pre-commit

Перед коммитом: Ruff (линт с --fix и формат), TypeScript при изменении файлов в `frontend/`, проверка YAML, концов файлов, детекция ключей и размера файлов.

```bash
pip install pre-commit
pre-commit install
```

Полный прогон: `pre-commit run --all-files`. Vulture выполняется только в CI.

---

## Деплой (Railway)

```bash
npm i -g @railway/cli
railway login
railway link
railway up --detach
```

В Railway указать корень репозитория. Сборка по Dockerfile: стадия фронта (build), затем образ Python с `static/` из `frontend/dist`. Старт: `alembic upgrade head && python web_server.py`.
