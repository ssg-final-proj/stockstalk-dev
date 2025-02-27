#!/bin/bash

# Docker Compose로 생성된 모든 컨테이너 중지 및 삭제
echo "모든 Docker Compose 컨테이너 중지 및 삭제 중..."
docker-compose down -v

# 마이그레이션 폴더 삭제
echo "마이그레이션 폴더 삭제 중..."
rm -rf auth_service/migrations
rm -rf portfolio_service/migrations
rm -rf exchange_service/migrations
rm -rf stock_kr_service/migrations

# 사용되지 않는 볼륨 삭제
echo "사용되지 않는 Docker 볼륨 삭제 중..."
docker volume prune -f

# 사용되지 않는 네트워크 삭제
echo "사용되지 않는 Docker 네트워크 삭제 중..."
docker network prune -f

# 사용되지 않는 이미지 삭제
echo "사용되지 않는 Docker 이미지 삭제 중..."
docker image prune -f

# 사용되지 않는 컨테이너 삭제
echo "사용되지 않는 Docker 컨테이너 삭제 중..."
docker container prune -f

echo "모든 설정이 정리되었습니다!"
