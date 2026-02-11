# i-make-nails

Telegram-бот и мини-приложение для записи к мастеру маникюра. Клиенты записываются на услуги через мини-апп, мастер управляет расписанием, услугами и списком клиентов через панель в том же приложении.

## Стек

Бэкенд: Python 3.13, aiogram 3, aiohttp. БД: PostgreSQL (в проде), SQLAlchemy 2, Alembic. Конфиг и валидация: Pydantic / pydantic-settings. Фронт мини-аппа: TypeScript, Vite, vanilla JS (без фреймворка), раздача через aiohttp из каталога `static/`. Тесты: pytest (unit + integration), Playwright (E2E). Качество кода: Ruff, pre-commit.

## Структура репозитория

```
├── bot/                    # Ядро бота и API мини-аппа
│   ├── api/                # HTTP API: deps, schemas, miniapp/routes
│   ├── config/             # Настройки из env
│   ├── database/           # Движок и сессии БД
│   ├── handlers/           # Обработчики Telegram (start и т.д.)
│   ├── models/             # SQLAlchemy-модели
│   └── services/           # Бизнес-логика (слоты, записи)
├── frontend/               # Исходники мини-аппа
│   ├── e2e/                # Спеки Playwright (клиент и мастер)
│   ├── scripts/            # start-e2e-server.mjs для E2E
│   └── src/                # Рендер клиента и мастера, API, стили
├── alembic/                # Миграции БД
├── tests/                  # unit и integration
├── web_server.py           # Точка входа: aiohttp, роуты, статика, при E2E — без бота
├── Dockerfile              # Многостадийная сборка: frontend + Python
├── Procfile, railway.json  # Деплой на Railway
└── .pre-commit-config.yaml # Ruff + pre-commit-hooks
```

Каталог `static/` в репозиторий не коммитится: это артефакт сборки. Он создаётся при `npm run build` в `frontend/` и копируется в корень при деплое (Dockerfile копирует `dist` в `static`) или при запуске E2E (скрипт `start-e2e-server.mjs` собирает фронт и копирует его в `static/` перед стартом сервера).

## Локальный запуск

Создать venv, поставить зависимости, поднять БД (PostgreSQL или для проверки SQLite с путём к файлу):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
```

Переменные окружения задать в `.env` или в системе: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY`, `MASTER_TELEGRAM_IDS`, `ADMIN_TELEGRAM_IDS`, `WEBHOOK_DOMAIN`. Для мини-аппа в режиме разработки: `MINIAPP_AUTH=dev` (тогда запросы без валидного initData, а по заголовку/query `X-Telegram-Id`).

Запуск сервера:

```bash
alembic upgrade head
python web_server.py
```

Порт по умолчанию 8000 (или `PORT` из env). Статику мини-аппа сервер отдаёт из `static/`; если каталога нет, нужно сначала собрать фронт (см. ниже) и скопировать `frontend/dist` в `static/` либо собрать через Docker.

Фронт (разработка и сборка):

```bash
cd frontend
npm install
npm run build    # результат в frontend/dist; для деплоя его копируют в корневой static/
```

## Тесты

Unit и integration (pytest):

```bash
pytest
```

E2E (Playwright): из корня репозитория, при свободном порту 8765:

```bash
cd frontend
npm run e2e
```

Перед E2E Playwright сам запускает сервер: собирает фронт, копирует его в `static/`, поднимает `web_server.py` с `E2E_SERVER=1` и файловой SQLite `e2e.db` (с сидом: один мастер, одна услуга, расписание). Ручной запуск сервера для E2E не нужен. Если порт 8765 занят, тесты падают с ошибкой о занятом порте.

## Pre-commit

В проекте настроен pre-commit: Ruff (линт и формат) и стандартные хуки (конфликты, YAML, концы файлов, пробелы, большие файлы). Чтобы хуки срабатывали при каждом коммите:

```bash
pip install pre-commit
pre-commit install
```

После этого при `git commit` будут запускаться проверки; при изменении файлов хуками коммит прервётся, нужно добавить изменения и коммитить снова. Разово прогнать по всем файлам: `pre-commit run --all-files`.

## Деплой (Railway)

Деплой через Railway CLI. Автодеплой по пушу в GitHub не настраивался.

```bash
npm i -g @railway/cli
railway login
railway link   # проект и сервис "i make nails"
railway up --detach
```

В настройках сервиса Root Directory — корень репозитория (`/`). Сборка по `Dockerfile`: сначала собирается фронт, затем образ Python с копированием `dist` в `static/`. Старт: `alembic upgrade head && python web_server.py`.
