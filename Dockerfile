FROM python:3.11-slim

# Установка DNS и обновление пакетов
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf && \
    apt-get update && \
    apt-get install -y gcc libffi-dev git iputils-ping curl  # Добавили сетевые утилиты

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir requests==2.31.0

COPY . .

CMD ["python", "bot.py"]
