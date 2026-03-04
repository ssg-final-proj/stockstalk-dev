# Stockstalk – Virtual Stock Simulation Service

대규모 트래픽을 가정하여 확장성과 가용성을 중심으로 설계한 모의 주식 투자 플랫폼입니다.  
AWS와 EKS 기반 MSA 구조로 구성하여 확장성과 자동 배포를 고려했습니다.

<img src="https://github.com/user-attachments/assets/9a42bf7f-f9a6-4ea1-92b8-7011976c09b6" width="900" />

## 프로젝트 소개

Stockstalk은 실제 주식 시장 데이터를 활용한 가상 투자 시뮬레이션 서비스입니다.  
사용자가 리스크 없이 투자 전략을 연습하고 금융 시장을 학습할 수 있도록 설계했습니다.

이 저장소는 서비스 백엔드 코드와 로컬 실행 환경을 함께 관리합니다.  
인증, 국내 주식 조회, 포트폴리오, 환전 기능을 각각 분리된 서비스로 구성했고, 일부 서버리스 기능은 별도 디렉터리에서 관리합니다.

<img width="900" alt="pp" src="https://github.com/user-attachments/assets/b4d0104c-34d4-4e3b-a75e-9e64ab8e1eba" />



## 저장소 구성

- `auth_service` : 로그인, 회원가입, 인증 처리
- `stock_kr_service` : 국내 주식 조회
- `portfolio_service` : 매수·매도, 보유 종목, 수익 계산
- `exchange_service` : 환율 조회 및 환전 처리
- `lambda` : 서버리스 기능 관련 코드
- `docker-compose.yaml` : 로컬 개발 환경
- `setup.sh` : 로컬 실행 스크립트

## 서비스 구조

애플리케이션은 MSA 구조로 구성되어 있습니다.  
클라이언트 요청은 각 서비스가 REST API로 처리하고, 주문/거래처럼 서비스 간 흐름이 이어지는 부분은 Kafka 기반 비동기 처리로 분리했습니다.

데이터는 RDS(MySQL)에 저장하고, Redis는 캐시와 보조 데이터 처리에 사용합니다.  
운영 환경에서는 Kubernetes 위에서 각 서비스를 개별적으로 배포하고 관리합니다.

## 운영 방식

실제 배포 환경은 EKS를 기준으로 구성했습니다.  
외부 요청은 Ingress를 통해 받아 서비스로 전달합니다.

또한 다음과 같은 운영 구성을 적용했습니다.

- HPA 기반 오토스케일링
- Liveness / Readiness Probe
- Kafka 기반 이벤트 처리
- Redis 캐시 운영

## 로컬 실행

사전 준비: Docker Desktop(권장), Docker Compose

```bash
# 실행 (권장)
./setup.sh

# 또는
docker-compose up --build -d

# 로그 확인
docker-compose logs -f
