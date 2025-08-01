FROM python:3.11-slim

# Установка DNS для обхода проблем в Китае
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Установка Python-зависимостей с китайским зеркалом
RUN pip install --no-cache-dir --default-timeout=100 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# Копируем исходный код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
