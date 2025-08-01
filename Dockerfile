FROM python:3.11-slim

# Исправление DNS
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Установка ВСЕХ необходимых зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Установка с китайским зеркалом и повышенным таймаутом
RUN pip install --no-cache-dir --default-timeout=300 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
