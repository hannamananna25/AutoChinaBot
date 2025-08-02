FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y gcc python3-dev libffi-dev libssl-dev

# Рабочая директория
WORKDIR /app

# Копирование всех файлов
COPY . .

# Установка прав на скрипт
RUN chmod +x start.sh

# Установка зависимостей и запуск бота
CMD ["./start.sh"]
