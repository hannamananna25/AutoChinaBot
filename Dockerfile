FROM python:3.11-slim

# Добавляем системные зависимости
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install requests==2.31.0
CMD ["python", "bot.py"]
