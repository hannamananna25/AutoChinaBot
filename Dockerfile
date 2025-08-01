FROM python:3.11-slim

# Исправление DNS для Китая
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование requirements.txt
COPY requirements.txt .

# Установка зависимостей с китайским зеркалом и повышенным таймаутом
RUN pip install --no-cache-dir --default-timeout=300 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# Копирование исходного кода
COPY . .

# Добавление диагностики
CMD ["sh", "-c", "pip list && python -c \"import requests; print(f'✅ requests установлена: {requests.__version__}')\" && python bot.py"]
