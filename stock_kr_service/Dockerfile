
# FROM python:3.9-slim

# WORKDIR /app

# # 프로젝트 루트 디렉토리의 전체 파일을 복사
# COPY . .

# # 필요한 도구 설치
# RUN apt-get update && apt-get install -y curl iputils-ping

# # 의존성 설치
# RUN pip install --no-cache-dir -r requirements.txt
# ENV FLASK_APP=app.app:create_app
# ENV FLASK_ENV=development
# CMD ["flask", "run", "--host=0.0.0.0", "--port=8002"]
# Dockerfile for stock_kr_service
FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y curl iputils-ping

RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8002"]
