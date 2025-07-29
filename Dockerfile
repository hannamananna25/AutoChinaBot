FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для парсинга XML и работы с SSL
RUN apt-get update && \
    apt-get install -y libxml2-dev libxslt-dev gcc libssl-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
