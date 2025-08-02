FROM python:3.11-slim
RUN apt-get update && apt-get install -y gcc python3-dev libffi-dev libssl-dev
WORKDIR /app
COPY . .
RUN chmod +x install_requests.sh
CMD ["./install_requests.sh"]
