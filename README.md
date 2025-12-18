# 🚀 Crypto Trading System

AWS ECS 기반 자동화된 암호화폐 트레이딩 시스템

## ⚡ 최신 업데이트: Scanner V2 (Redis 기반)

**Redis 기반 Discovery + Scanner V2 아키텍처 배포 준비 완료!**

- ✅ Discovery Service: 동적 Top N 심볼 선정
- ✅ Scanner V2 Service: 실시간 WebSocket 감시 (Auto-scaling 1-10)
- ✅ ElastiCache Redis: 상태 저장소 + Pub/Sub
- ✅ 컨테이너당 50개 심볼 처리
- ✅ 원클릭 배포 스크립트

**배포 방법**: `./scripts/deploy-redis-services.sh`

📚 **상세 문서**:
- [ECS_배포_완료.md](./ECS_배포_완료.md) - 한글 요약
- [ECS_DEPLOYMENT_GUIDE.md](./ECS_DEPLOYMENT_GUIDE.md) - 전체 가이드
- [QUICK_DEPLOY.md](./QUICK_DEPLOY.md) - 빠른 배포

---

## 📁 프로젝트 구조

```
crypto-trading-system/
├── services/              # 마이크로서비스
│   ├── discovery/        # 🆕 Discovery Service (Redis 기반)
│   ├── scanner/          # 🆕 Scanner V2 (Redis 기반, WebSocket)
│   ├── analyzer/         # 백테스팅 분석
│   ├── selector/         # 최적 전략 선택
│   ├── finder/           # 진입 신호 탐색
│   └── executor/         # 주문 실행
├── src/                   # 공통 라이브러리
│   ├── backtesting/      # 백테스팅 엔진
│   ├── scanning/         # 스캐닝 로직
│   ├── strategies/       # 트레이딩 전략
│   └── utils/            # 유틸리티
├── config/                # 설정 파일
├── infrastructure/        # 인프라 코드 (Terraform)
│   └── terraform/
│       ├── main.tf       # 기존 인프라
│       ├── redis.tf      # 🆕 ElastiCache Redis
│       └── discovery_scanner.tf  # 🆕 Discovery + Scanner ECS
├── scripts/               # 배포 스크립트
│   └── deploy-redis-services.sh  # 🆕 Redis 서비스 배포
├── docs/                  # 문서
└── archive/               # 아카이브
```

## 🚀 빠른 시작

### Scanner V2 배포 (Redis 기반) 🆕

```bash
# 1. Secrets Manager 설정 (최초 1회)
aws secretsmanager create-secret \
    --name crypto-backtest/bybit-api-key \
    --secret-string "your-api-key" \
    --region ap-northeast-2

# 2. 배포 실행
./scripts/deploy-redis-services.sh

# 3. 로그 확인
aws logs tail /ecs/crypto-backtest-discovery --follow
aws logs tail /ecs/crypto-backtest-scanner-v2 --follow
```

### 기존 시스템 배포

```bash
# 1. 인프라 배포
./scripts/deploy-infrastructure.sh

# 2. Docker 이미지 빌드 및 푸시
./scripts/build-and-push.sh

# 3. ECS 서비스 업데이트
./scripts/update-services.sh
```

## 📊 시스템 아키텍처

### 🆕 Scanner V2: Redis 기반 실시간 감시

```
┌─────────────────────────────────────────────────────────┐
│                    AWS ECS Cluster                       │
│                                                           │
│  ┌──────────────┐              ┌──────────────────────┐ │
│  │ Discovery    │              │  Scanner V2          │ │
│  │  (1개 고정)   │              │  (1-10개 Auto-scale) │ │
│  │              │              │                      │ │
│  │ • 1분마다    │              │ • 컨테이너당 50개    │ │
│  │ • Top N 선정 │              │ • WebSocket 실시간   │ │
│  │ • Redis 저장 │              │ • 기회 감지          │ │
│  └──────┬───────┘              └──────────┬───────────┘ │
│         │                                  │             │
└─────────┼──────────────────────────────────┼─────────────┘
          │                                  │
          └──────────┬───────────────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │ ElastiCache      │
          │ Redis            │
          │ • 상태 저장소     │
          │ • Pub/Sub        │
          └──────────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │ Amazon MQ        │
          │ RabbitMQ         │
          │ • 기회 신호 큐    │
          └──────────────────┘
```

### 기존: 백테스팅 파이프라인

```
Scanner V2 (24/7 WebSocket)
  - 300+ 코인 실시간 모니터링
  - BB 슈쿼즈, 호가 불균형, 거래량 스파이크 감지
  ↓ RabbitMQ (opportunity-queue)
Finder (Auto-scaling 1-5)
  - 실시간 진입 신호 정밀 분석
  ↓ DynamoDB
Executor (5초마다)
  ↓ Bybit API
```

### 기존 백테스팅 모드 (병행 운영)

```
Scanner (1시간마다)
  ↓ RabbitMQ
Analyzer (Auto-scaling 1-10)
  ↓ DynamoDB
Selector (1분마다)
  ↓ RabbitMQ
Finder (Auto-scaling 1-5)
  ↓ DynamoDB
Executor (5초마다)
  ↓ Bybit API
```

## 🔧 환경 변수

`.env.example`을 참고하여 `.env` 파일을 생성하세요.

## 📚 문서

### 핵심 가이드
- 🆕 [Scanner V2 가이드](docs/SCANNER_V2_GUIDE.md) - 실시간 스캘핑 레이더
- [시스템 아키텍처](docs/SYSTEM_ARCHITECTURE.md) - 전체 시스템 구조
- [배포 가이드](docs/DEPLOYMENT_GUIDE.md)
- [트레이딩 시스템 가이드](docs/TRADING_SYSTEM_GUIDE.md)
- [주문 실행 가이드](docs/ORDER_EXECUTION_GUIDE.md)

### 추가 문서
- [백테스팅 개선 사항](docs/BACKTEST_IMPROVEMENTS.md)
- [Scanner Service README](services/scanner/README.md)

## 🛠️ 기술 스택

- **언어**: Python 3.11
- **클라우드**: AWS (ECS, DynamoDB, RabbitMQ, ECR)
- **인프라**: Terraform
- **메시지 큐**: Amazon MQ (RabbitMQ)
- **거래소**: Bybit

## ⚙️ 주요 설정

### Strategy Selector 필터
- 최소 승률: 40%
- 최소 수익: $50
- 최소 거래 수: 10개

### Order Executor
- 포지션 크기: $100
- 레버리지: 10x
- 스캔 주기: 5초

## 📈 모니터링

### ECS 서비스 상태 확인
```bash
aws ecs describe-services \
  --cluster crypto-backtest-cluster \
  --services crypto-backtest-analyzer crypto-backtest-finder crypto-backtest-executor
```

### CloudWatch 로그 확인
```bash
aws logs tail /ecs/crypto-backtest-analyzer --follow
```

### DynamoDB 데이터 확인
```bash
aws dynamodb scan --table-name crypto-backtest-results --max-items 5
```

## 🔐 보안

- Bybit API 키는 AWS Secrets Manager에 저장
- ECS 태스크는 IAM 역할을 통해 권한 관리
- RabbitMQ는 SSL/TLS 연결 사용

## 📝 라이센스

Private Project

## 👥 기여

이 프로젝트는 개인 프로젝트입니다.
