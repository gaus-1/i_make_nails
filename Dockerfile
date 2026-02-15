# Stage 1: build frontend
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build && rm -rf node_modules

# Stage 2: Python app + static
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/dist ./static
RUN rm -rf tests frontend .git .dockerignore .env.example \
    && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec python web_server.py"]
