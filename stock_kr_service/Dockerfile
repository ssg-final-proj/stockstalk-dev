FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y curl iputils-ping

# ✅ 핵심: Python 경로 설정 추가
ENV PYTHONPATH="/app/app:${PYTHONPATH}"

RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8002"]