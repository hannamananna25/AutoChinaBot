FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -c constraints.txt -r requirements.txt

CMD ["python", "bot.py"]