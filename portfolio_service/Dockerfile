FROM python:3.9-slim

WORKDIR /app

COPY ../../config.py ./config.py
COPY ../../db.py ./db.py
COPY ../../.env .env

RUN apt-get update && apt-get install -y curl iputils-ping

RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8003"]
