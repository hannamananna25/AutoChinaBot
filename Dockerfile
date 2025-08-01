FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей и очистка кэша
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python-зависимости с увеличенным таймаутом
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Копируем исходный код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
