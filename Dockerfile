FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y gcc python3-dev libffi-dev libssl-dev

# Рабочая директория
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir requests==2.31.0  # Явная принудительная установка

# Копирование исходного кода
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
