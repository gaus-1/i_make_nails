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

## Локальный запуск (будет дополняться)

> Деплой: Railway (Dockerfile).

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
