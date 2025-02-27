#!/bin/bash

# Docker 이미지 빌드 및 컨테이너 시작
echo "Docker 이미지 빌드 및 컨테이너 시작 중..."
docker-compose up --build -d

# 컨테이너가 준비될 때까지 기다리기
echo "컨테이너가 준비될 때까지 기다리는 중..."
sleep 5  # 컨테이너가 완전히 뜰 때까지 대기

echo "초기 설정 완료!"
