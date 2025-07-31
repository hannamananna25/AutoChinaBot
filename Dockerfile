FROM python:3.11-alpine

# Добавляем системные зависимости
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
