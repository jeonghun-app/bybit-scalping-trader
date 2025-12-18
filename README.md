# Crypto Trading System

AWS ECS 기반 자동화된 암호화폐 트레이딩 시스템

## 📁 프로젝트 구조

```
crypto-trading-system/
├── services/              # 마이크로서비스
│   ├── scanner/          # 변동성 높은 코인 스캔
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
├── scripts/               # 배포 스크립트
├── docs/                  # 문서
└── archive/               # 아카이브 (백테스트 결과 등)
```

## 🚀 빠른 시작

### 1. 인프라 배포

```bash
./scripts/deploy-infrastructure.sh
```

### 2. Docker 이미지 빌드 및 푸시

```bash
./scripts/build-and-push.sh
```

### 3. ECS 서비스 업데이트

```bash
./scripts/update-services.sh
```

## 📊 시스템 아키텍처

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

- [배포 가이드](docs/DEPLOYMENT_GUIDE.md)
- [트레이딩 시스템 가이드](docs/TRADING_SYSTEM_GUIDE.md)
- [주문 실행 가이드](docs/ORDER_EXECUTION_GUIDE.md)
- [백테스팅 개선 사항](docs/BACKTEST_IMPROVEMENTS.md)

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
