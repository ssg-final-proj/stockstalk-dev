# Dockerfile for auth_service
FROM python:3.9-slim

WORKDIR /app

# 루트 디렉토리의 공통 파일들과 .env 파일을 복사
COPY ../config.py ./config.py
COPY ../db.py ./db.py
COPY ../.env .env
COPY . .

RUN apt-get update && apt-get install -y curl iputils-ping

RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8001"]
