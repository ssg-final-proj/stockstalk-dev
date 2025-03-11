FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y curl iputils-ping

# 최신 pip 및 setuptools 설치
RUN pip install --upgrade pip setuptools

# 의존성 설치 (캐시 비활성화 및 신뢰할 수 있는 호스트 추가)
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8004"]