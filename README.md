# Stockstalk – Virtual Stock Simulation Service

확장성과 운영 환경을 고려해 설계한 가상 주식 투자 시뮬레이션 플랫폼입니다.
AWS와 EKS 기반 MSA 구조를 바탕으로 서비스 분리, 이벤트 기반 처리, 자동 배포 환경을 고려했습니다.

<img src="https://github.com/user-attachments/assets/9a42bf7f-f9a6-4ea1-92b8-7011976c09b6" width="900" />

---

## 프로젝트 소개

Stockstalk은 실제 주식 시장 데이터를 활용한 **가상 투자 시뮬레이션 서비스**입니다.  
사용자가 리스크 없이 투자 전략을 실험하고 시장 흐름을 학습할 수 있도록 설계했습니다.

이 저장소는 **서비스 백엔드 코드와 로컬 실행 환경**을 함께 관리합니다.  
인증, 국내 주식 조회, 포트폴리오 관리, 환전 기능을 각각 독립 서비스로 구성했고 일부 서버리스 기능은 별도 디렉터리에서 관리합니다.

<img width="900" alt="pp" src="https://github.com/user-attachments/assets/b4d0104c-34d4-4e3b-a75e-9e64ab8e1eba" />

---

## Repository Structure

```
stockstalk-dev
├─ auth_service          # 인증 / 사용자 계정
├─ stock_kr_service      # 국내 주식 조회 / 주문 생성
├─ portfolio_service     # 자산 관리 / 수익 계산 / 랭킹
├─ exchange_service      # 환율 조회 / 환전
├─ lambda                # 서버리스 기능 코드
├─ docker-compose.yaml   # 로컬 실행 환경
├─ setup.sh              # 로컬 실행 스크립트
└─ .github/workflows     # CI (Docker build / ECR push)
```

---

## Service Architecture

서비스는 기능 기준으로 다음과 같이 분리했습니다.

| Service | 역할 |
|---|---|
| auth_service | 로그인 및 사용자 인증 |
| stock_kr_service | 주식 조회 및 주문 생성 |
| portfolio_service | 주문 반영 / 포트폴리오 계산 |
| exchange_service | 환율 조회 및 환전 |

사용자 흐름 기준으로 보면 대략 아래 순서로 이어집니다.

```
auth → stock → portfolio
```

환전 기능은 투자 흐름과 분리된 별도 서비스로 구성했습니다.

---

## Core Architecture

애플리케이션은 **MSA 기반 구조**로 설계했습니다.

- REST API 기반 서비스 통신
- Kafka 기반 비동기 이벤트 처리
- Redis 캐시 계층
- Kubernetes 기반 서비스 배포

각 구성요소 역할은 다음과 같습니다.

| Component | 역할 |
|---|---|
| MySQL (RDS) | 사용자 / 주문 / 포트폴리오 데이터 저장 |
| Redis | 주식 조회 캐시, 환율 캐시, 세션 관리 |
| Kafka | 주문 이벤트 전달 및 서비스 간 비동기 처리 |
| WebSocket | 주문 상태 / 포트폴리오 변경 실시간 반영 |

---

## Event Flow

### Stock Price Request

```
User
→ stock_kr_service
→ External Stock API
→ Redis Cache
→ Response
```

### Order Processing

주문 생성과 자산 반영을 Kafka 이벤트로 분리하여 서비스 간 결합도를 낮추는 구조로 구성했습니다.

```
User
→ stock_kr_service
→ Kafka Event
→ portfolio_service
→ Database Update
→ WebSocket Push
```

### Exchange Flow

```
User
→ exchange_service
→ Exchange Rate API
→ Redis Cache
→ Database Update
```

---

## Deployment Architecture

운영 환경은 **AWS EKS 기반 Kubernetes 클러스터**를 기준으로 구성했습니다.

```
Internet
  ↓
ALB
  ↓
Ingress
  ↓
Service
  ↓
Pod
```

주요 운영 구성

- Horizontal Pod Autoscaler
- Liveness / Readiness Probe
- Kafka 기반 이벤트 처리
- Redis 캐시 계층
- ConfigMap / Secret 기반 환경 설정 관리

---

## Data Storage

데이터는 **MySQL(RDS)** 기반으로 관리하며 하나의 DB 인스턴스 내부에서 스키마를 분리하는 방식으로 구성했습니다.

사용 스키마

- `auth_db`
- `portfolio_db`
- `exchange_db`

서비스 규모 확장 시에는 서비스별 독립 데이터베이스 구조로 분리하는 방식으로 확장할 수 있도록 설계했습니다.

---

## CI (Docker Build & ECR Push)

Docker 이미지는 GitHub Actions를 통해 자동 빌드됩니다.

```
GitHub Actions
   ↓
Docker Build
   ↓
ECR Push
   ↓
Kubernetes Deployment
```

변경된 서비스 기준으로 이미지를 빌드하여 ECR로 push하도록 구성했습니다.

---

## Local Development

사전 준비

- Docker Desktop
- Docker Compose

실행 방법

```bash
# 권장 실행 방법
./setup.sh

# 또는 직접 실행
docker-compose up --build -d

# 로그 확인
docker-compose logs -f
```

---

## Improvements

- 초기 구현에서는 **카카오 로그인만 지원**하는 구조로 사용자 식별자를 `kakao_id` 기준으로 사용  
  → 향후 소셜 로그인 확장 또는 일반 로그인 도입 시 **내부 사용자 PK 기반 식별 구조로 통합 필요**

- 서비스 간 통신은 **REST API + Kafka 이벤트 기반 구조**로 구성  
  → 현재 서비스 규모에서는 충분하지만, 서비스가 더 증가할 경우  
  **Service Mesh(Istio 등) 기반 트래픽 관리 및 observability 도입 검토 가능**

- Kafka 메시지는 JSON 기반 이벤트 형태로 구현  
  → 서비스 규모 확장 시 **메시지 구조 관리 체계(Schema Registry 등) 도입 검토 가능**

- 금융 데이터 계산에 `FLOAT` 사용  
  → 실제 금융 서비스에서는 **DECIMAL 타입 사용이 더 적절**

- Docker 이미지 태그를 `latest` 기준으로 사용  
  → 배포 추적성을 위해 **Git SHA 기반 태그 전략 적용 필요**

- 현재 DB 구조는 **MySQL 내부 스키마 분리 방식**  
  → 서비스 규모 확장 시 **서비스별 독립 DB 구조 (ex: 서비스별 RDS)** 로 분리 가능
