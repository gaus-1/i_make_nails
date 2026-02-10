# i-make-nails bot

Telegram-бот и мини-приложение для записи к мастеру маникюра.

## Кратко о проекте

- Один бот и мини-апп в Telegram.
- В центре — мастер (сейчас один), около сотни постоянных клиентов.
- Клиенты сами записываются на услуги, мастер управляет расписанием, услугами и списком клиентов.

## Стек

- Python 3.13, aiogram 3, aiohttp
- PostgreSQL 17, SQLAlchemy 2, Alembic
- Pydantic / pydantic-settings для конфигурации
- Ruff + pre-commit для качества кода

## Деплой (Railway)

Деплой **только через Railway CLI** (автодеплой по пушу в GitHub не настроен):

```bash
npm i -g @railway/cli
railway login
railway link   # выбрать проект "i make nails" и сервис
railway up --detach
```

Сборка по `Dockerfile` в корне. Root Directory в настройках сервиса должен быть `/`.

## Локальный запуск (будет дополняться)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
