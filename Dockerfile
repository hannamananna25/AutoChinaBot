FROM python:3.11

WORKDIR /app

# Копируем зависимости первыми для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВСЕ файлы включая .env
COPY . .

# Принудительно указываем путь к .env
CMD ["python", "-c", "from dotenv import load_dotenv; load_dotenv('/app/.env'); import bot"]
