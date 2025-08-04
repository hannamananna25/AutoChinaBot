cat > /root/AutoChinaBot/Dockerfile <<EOF
FROM python:3.11-slim-bookworm
WORKDIR /app

# Настройка альтернативных DNS (Cloudflare и Google)
RUN echo "nameserver 1.1.1.1" > /etc/resolv.conf && \
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \\
    libxml2 \\
    libxslt1.1 \\
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости отдельно для кэширования
COPY requirements.txt .

# Установка Python-зависимостей с зеркалами и увеличенным таймаутом
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir --default-timeout=100 \\
        -r requirements.txt \\
        -i https://pypi.tuna.tsinghua.edu.cn/simple \\
        -i https://mirrors.aliyun.com/pypi/simple/ \\
        -i https://pypi.doubanio.com/simple/

# Копируем остальные файлы
COPY . .

CMD ["python", "bot.py"]
EOF
