FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y gcc libffi-dev git

# Копируем только requirements.txt сначала для кэширования
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Явная установка requests на случай проблем
RUN pip install --no-cache-dir requests==2.31.0

# Копируем остальные файлы
COPY . .

# Запускаем скрипт
CMD ["python", "bot.py"]
