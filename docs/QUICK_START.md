# 🚀 빠른 시작 가이드

## VPC `vpc-07a289adc49898e52`에 ECS 배포

### ⚡ 원클릭 배포

```bash
./deploy.sh
```

이 스크립트가 자동으로:
1. ✅ ECR 리포지토리 생성
2. ✅ Docker 이미지 빌드 및 푸시
3. ✅ Terraform으로 인프라 배포
4. ✅ ECS, RabbitMQ, DynamoDB 설정

---

## 📋 사전 준비 (5분)

### 1. AWS CLI 설정
```bash
aws configure
# Region: ap-northeast-2
```

### 2. Bybit API 키 설정
```bash
aws secretsmanager create-secret \
  --name crypto-backtest/bybit-api-key \
  --secret-string "YOUR_BYBIT_API_KEY" \
  --region ap-northeast-2

aws secretsmanager create-secret \
  --name crypto-backtest/bybit-api-secret \
  --secret-string "YOUR_BYBIT_API_SECRET" \
  --region ap-northeast-2
```

### 3. 배포 실행
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 🔍 배포 확인 (2분)

### Scanner 수동 실행 (테스트)
```bash
# 서브넷 ID 가져오기
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=vpc-07a289adc49898e52" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region ap-northeast-2)

# Security Group ID 가져오기
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=vpc-07a289adc49898e52" "Name=group-name,Values=crypto-backtest-ecs-tasks" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --region ap-northeast-2)

# Scanner 실행
aws ecs run-task \
  --cluster crypto-backtest-cluster \
  --task-definition crypto-backtest-scanner \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ID}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
  --region ap-northeast-2
```

### 로그 확인
```bash
# Scanner 로그 (실시간)
aws logs tail /ecs/crypto-backtest-scanner --follow --region ap-northeast-2

# Analyzer 로그 (실시간)
aws logs tail /ecs/crypto-backtest-analyzer --follow --region ap-northeast-2
```

### DynamoDB 데이터 확인
```bash
# 최신 결과 조회
aws dynamodb scan \
  --table-name crypto-backtest-results \
  --max-items 5 \
  --region ap-northeast-2
```

---

## 📊 예상 결과

### 1시간 후:
- ✅ Scanner가 자동 실행 (EventBridge)
- ✅ 30개 코인 스캔 완료
- ✅ RabbitMQ에 150개 태스크 발행
- ✅ Analyzer가 태스크 소비 시작
- ✅ DynamoDB에 결과 저장

### DynamoDB 데이터 예시:
```json
{
  "symbol": "BTCUSDT",
  "scan_timestamp": 1702800000,
  "timeframes": {
    "1m": {
      "total_trades": 234,
      "win_rate": 56.4,
      "total_pnl": 679.20
    },
    "3m": { ... },
    "5m": { ... }
  },
  "optimal_timeframe": "1m",
  "optimal_pnl": 679.20
}
```

---

## 🔧 문제 해결

### Scanner가 실행되지 않음?
```bash
# EventBridge Rule 확인
aws events describe-rule \
  --name crypto-backtest-scanner-schedule \
  --region ap-northeast-2

# 수동 실행으로 테스트 (위 명령어 참고)
```

### Analyzer가 메시지를 소비하지 않음?
```bash
# ECS Service 상태 확인
aws ecs describe-services \
  --cluster crypto-backtest-cluster \
  --services crypto-backtest-analyzer \
  --region ap-northeast-2

# 로그 확인
aws logs tail /ecs/crypto-backtest-analyzer --follow --region ap-northeast-2
```

### RabbitMQ 연결 실패?
```bash
# Security Group 확인
aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=vpc-07a289adc49898e52" \
  --region ap-northeast-2

# RabbitMQ 엔드포인트 확인
aws mq list-brokers --region ap-northeast-2
```

---

## 💰 비용

**월간 예상 비용: ~$135**
- ECS Fargate: $105/월
- Amazon MQ: $18/월
- DynamoDB: $5/월
- CloudWatch: $5/월
- 기타: $2/월

**비용 절감:**
- Spot Instance 사용: -70%
- 스캔 주기 2시간: -50%

---

## 🗑️ 삭제

```bash
cd infrastructure/terraform
terraform destroy
```

---

## 📚 상세 가이드

- **배포 가이드**: `DEPLOYMENT_GUIDE.md`
- **DynamoDB 스키마**: `infrastructure/dynamodb_schema.md`
- **타임프레임 분석**: `TIMEFRAME_ANALYSIS_GUIDE.md`

---

## 🆘 지원

문제 발생 시:
1. CloudWatch Logs 확인
2. `DEPLOYMENT_GUIDE.md` 트러블슈팅 섹션 참고
3. Security Group 및 IAM 권한 확인
