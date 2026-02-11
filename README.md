# i-make-nails

Telegram-бот и мини-приложение для записи клиентов к мастеру маникюра. Клиенты выбирают дату и время в мини-аппе, мастер ведёт расписание, клиентов и настройки в той же среде.

**Цель проекта** — убрать необходимость вести очередь в блокноте и разгрузить личные сообщения в Telegram: запись и переносы происходят в мини-аппе, без бесконечных «на какое число свободно?» в личку.

---

## Стек

**Бэкенд:** Python 3.13, aiogram 3, aiohttp. БД: PostgreSQL (прод), SQLAlchemy 2, Alembic. Конфиг: Pydantic / pydantic-settings.

**Фронт мини-аппа:** TypeScript, Vite, раздача статики из `static/` через aiohttp.

**Тесты:** pytest (unit, integration), Vitest (frontend), Playwright (E2E). Качество: Ruff, Vulture (в CI), pre-commit (Ruff, TypeScript, проверка секретов и размера файлов).

---

## Структура репозитория

```
├── .github/workflows/      # CI: Ruff, pytest, Vitest, сборка и attestation
├── bot/                    # Бот и API мини-аппа
│   ├── api/                # HTTP API: deps, schemas, miniapp/routes
│   ├── config/             # Настройки из env
│   ├── database/           # Движок и сессии БД
│   ├── handlers/           # Обработчики Telegram (start и т.д.)
│   ├── models/             # SQLAlchemy-модели
│   └── services/           # Бизнес-логика: слоты, записи
├── frontend/               # Мини-апп
│   ├── e2e/                # Playwright: клиент и мастер
│   ├── scripts/            # E2E-сервер, сборка
│   └── src/                # Рендер, API, стили, тесты Vitest
├── scripts/                # check-frontend-tsc.mjs для pre-commit
├── alembic/                # Миграции БД
├── tests/                  # pytest: unit, integration
├── web_server.py           # Точка входа: aiohttp, роуты, статика
├── Dockerfile              # Сборка: frontend → Python + static
├── Procfile, railway.json  # Деплой на Railway
├── package.json            # Скрипты тестов из корня (npm test, test:all)
└── .pre-commit-config.yaml # Ruff, pre-commit-hooks, проверка фронта
```

Каталог `static/` в репозиторий не входит: это артефакт сборки. Он создаётся при `npm run build` в `frontend/` и при деплое копируется из `frontend/dist` (Dockerfile или E2E-скрипт).

---

## Локальный запуск

Создать venv и установить зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

В `.env` или в окружении задать: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY`, `MASTER_TELEGRAM_IDS`, `ADMIN_TELEGRAM_IDS`, `WEBHOOK_DOMAIN`. Для разработки мини-аппа: `MINIAPP_AUTH=dev` (запросы без валидного initData, по заголовку/query `X-Telegram-Id`).

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

Для деплоя образ копирует `frontend/dist` в `static/` при сборке.

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
cd frontend && npm run test -- --run
# или из корня:
npm test
```

**Всё (Vitest + pytest):**

```bash
npm run test:all
```

**E2E (Playwright):** порт 8765 должен быть свободен.

```bash
cd frontend
npm run e2e
```

Playwright сам собирает фронт, копирует в `static/`, поднимает сервер с `E2E_SERVER=1` и SQLite `e2e.db` (сид: один мастер, услуга, расписание). Ручной запуск сервера не нужен.

---

## Pre-commit

При коммите запускаются: Ruff (линт и формат для Python), проверка TypeScript во фронте (`tsc --noEmit` при изменениях в `frontend/`), проверка конфликтов слияния, YAML, концы файлов, пробелы, размер добавляемых файлов (до 600 KB), детекция приватных ключей.

Установка:

```bash
pip install pre-commit
pre-commit install
```

Разовый прогон по всем файлам: `pre-commit run --all-files`.

Vulture (мёртвый код) выполняется только в CI, не в pre-commit.

---

## Деплой (Railway)

Через Railway CLI:

```bash
npm i -g @railway/cli
railway login
railway link
railway up --detach
```

Root Directory сервиса — корень репозитория. Сборка по `Dockerfile`: фронт, затем образ Python с `static/` из `dist`. Старт: `alembic upgrade head && python web_server.py`.
