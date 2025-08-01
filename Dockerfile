FROM python:3.11-alpine

WORKDIR /app

# Установка системных зависимостей
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Явно устанавливаем requests
RUN pip install requests==2.31.0

CMD ["python", "bot.py"]
