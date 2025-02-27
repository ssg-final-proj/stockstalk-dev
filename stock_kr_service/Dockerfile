FROM python:3.9-slim

WORKDIR /app

# 현재 디렉토리의 모든 파일을 복사
COPY . .

RUN apt-get update && apt-get install -y curl iputils-ping

# 필요한 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8002"]