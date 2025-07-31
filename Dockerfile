FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Гарантированная установка requests
RUN pip install requests==2.31.0

CMD ["python", "bot.py"]
