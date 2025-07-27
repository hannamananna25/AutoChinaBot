FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Обновляем pip и устанавливаем виртуальное окружение
RUN pip install --upgrade pip setuptools wheel && \
    python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Копируем и устанавливаем зависимости из requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
