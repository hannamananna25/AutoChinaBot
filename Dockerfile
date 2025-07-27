FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости для psycopg2 и чистки
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Кэшируем установку зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем только необходимые файлы
COPY bot.py .

# Используем PORT от Railway
ENV PORT=8000
EXPOSE $PORT

# Запускаем приложение
CMD ["python", "bot.py"]
