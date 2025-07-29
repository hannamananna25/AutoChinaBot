FROM python:3.11-slim

# Используем зеркало для надежности
RUN sed -i 's/deb.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list

WORKDIR /app

# Установка зависимостей
RUN apt-get update && \
    apt-get install -y gcc python3-dev libxml2-dev libxslt-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
