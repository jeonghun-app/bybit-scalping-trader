# ECS 배포 가이드

## 🎯 아키텍처 개요

```
VPC: vpc-07a289adc49898e52
│
├── Scanner Service (ECS Scheduled Task)
│   └── 1시간마다 실행
│   └── 변동성 30개 코인 스캔
│   └── RabbitMQ에 150개 태스크 발행 (30코인 × 5타임프레임)
│
├── RabbitMQ (Amazon MQ)
│   └── Queue: backtest-tasks
│   └── 메시지 브로커
│
├── Analyzer Service (ECS Service)
│   └── Auto-scaling: 1-10 컨테이너
│   └── RabbitMQ에서 태스크 소비
│   └── 백테스팅 수행
│   └── DynamoDB에 결과 저장
│
└── DynamoDB
    ├── crypto-backtest-results (백테스트 결과)
    └── crypto-scan-history (스캔 히스토리)
```

---

## 📋 사전 준비

### 1. AWS CLI 설정
```bash
aws configure
# AWS Access Key ID: YOUR_KEY
# AWS Secret Access Key: YOUR_SECRET
# Default region: ap-northeast-2
```

### 2. Terraform 설치
```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### 3. Docker 설치 및 로그인
```bash
# Docker 설치 확인
docker --version

# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-northeast-2.amazonaws.com
```

---

## 🚀 배포 단계

### Step 1: ECR 리포지토리 생성

```bash
# Scanner 리포지토리
aws ecr create-repository \
  --repository-name crypto-backtest-scanner \
  --region ap-northeast-2

# Analyzer 리포지토리
aws ecr create-repository \
  --repository-name crypto-backtest-analyzer \
  --region ap-northeast-2
```

### Step 2: Docker 이미지 빌드 및 푸시

```bash
# AWS Account ID 가져오기
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-northeast-2

# Scanner 이미지 빌드
docker build -f Dockerfile.scanner -t crypto-backtest-scanner:latest .

# Scanner 이미지 태그 및 푸시
docker tag crypto-backtest-scanner:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-scanner:latest

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-scanner:latest

# Analyzer 이미지 빌드
docker build -f Dockerfile.analyzer -t crypto-backtest-analyzer:latest .

# Analyzer 이미지 태그 및 푸시
docker tag crypto-backtest-analyzer:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-analyzer:latest

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-analyzer:latest
```

### Step 3: Secrets Manager에 API 키 저장

```bash
# Bybit API 키 저장
aws secretsmanager create-secret \
  --name crypto-backtest/bybit-api-key \
  --secret-string "YOUR_BYBIT_API_KEY" \
  --region ap-northeast-2

aws secretsmanager create-secret \
  --name crypto-backtest/bybit-api-secret \
  --secret-string "YOUR_BYBIT_API_SECRET" \
  --region ap-northeast-2
```

### Step 4: Terraform으로 인프라 배포

```bash
cd infrastructure/terraform

# Terraform 초기화
terraform init

# 배포 계획 확인
terraform plan

# 배포 실행
terraform apply

# 확인 후 'yes' 입력
```

**배포되는 리소스:**
- ✅ ECS Cluster
- ✅ RabbitMQ (Amazon MQ)
- ✅ DynamoDB 테이블 2개
- ✅ Security Groups
- ✅ IAM Roles
- ✅ CloudWatch Log Groups
- ✅ EventBridge Rule (1시간 스케줄)
- ✅ ECS Task Definitions
- ✅ ECS Service (Analyzer)
- ✅ Auto Scaling

---

## 🔍 배포 확인

### 1. ECS 클러스터 확인
```bash
aws ecs list-clusters --region ap-northeast-2

aws ecs describe-clusters \
  --clusters crypto-backtest-cluster \
  --region ap-northeast-2
```

### 2. RabbitMQ 확인
```bash
aws mq list-brokers --region ap-northeast-2

# RabbitMQ 관리 콘솔 접속
# URL: https://[broker-id].mq.ap-northeast-2.amazonaws.com
# Username: admin
# Password: (Terraform output에서 확인)
```

### 3. DynamoDB 테이블 확인
```bash
aws dynamodb list-tables --region ap-northeast-2

aws dynamodb describe-table \
  --table-name crypto-backtest-results \
  --region ap-northeast-2
```

### 4. Scanner 수동 실행 (테스트)
```bash
aws ecs run-task \
  --cluster crypto-backtest-cluster \
  --task-definition crypto-backtest-scanner \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --region ap-northeast-2
```

### 5. 로그 확인
```bash
# Scanner 로그
aws logs tail /ecs/crypto-backtest-scanner --follow --region ap-northeast-2

# Analyzer 로그
aws logs tail /ecs/crypto-backtest-analyzer --follow --region ap-northeast-2
```

---

## 📊 모니터링

### CloudWatch 대시보드
```bash
# ECS 메트릭
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=crypto-backtest-analyzer \
  --start-time 2025-12-17T00:00:00Z \
  --end-time 2025-12-17T23:59:59Z \
  --period 3600 \
  --statistics Average \
  --region ap-northeast-2
```

### DynamoDB 데이터 조회
```bash
# 최신 백테스트 결과 조회
aws dynamodb query \
  --table-name crypto-backtest-results \
  --key-condition-expression "symbol = :symbol" \
  --expression-attribute-values '{":symbol":{"S":"BTCUSDT"}}' \
  --scan-index-forward false \
  --limit 1 \
  --region ap-northeast-2
```

---

## 🔧 트러블슈팅

### 문제 1: Scanner가 실행되지 않음
```bash
# EventBridge Rule 확인
aws events describe-rule \
  --name crypto-backtest-scanner-schedule \
  --region ap-northeast-2

# Target 확인
aws events list-targets-by-rule \
  --rule crypto-backtest-scanner-schedule \
  --region ap-northeast-2

# 수동 실행으로 테스트
aws ecs run-task \
  --cluster crypto-backtest-cluster \
  --task-definition crypto-backtest-scanner \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --region ap-northeast-2
```

### 문제 2: Analyzer가 메시지를 소비하지 않음
```bash
# RabbitMQ 큐 확인
# 관리 콘솔에서 확인: https://[broker-id].mq.ap-northeast-2.amazonaws.com

# ECS Service 상태 확인
aws ecs describe-services \
  --cluster crypto-backtest-cluster \
  --services crypto-backtest-analyzer \
  --region ap-northeast-2

# Task 로그 확인
aws logs tail /ecs/crypto-backtest-analyzer --follow --region ap-northeast-2
```

### 문제 3: DynamoDB 쓰기 실패
```bash
# IAM 권한 확인
aws iam get-role-policy \
  --role-name crypto-backtest-ecs-task \
  --policy-name crypto-backtest-ecs-task-policy \
  --region ap-northeast-2

# DynamoDB 테이블 상태 확인
aws dynamodb describe-table \
  --table-name crypto-backtest-results \
  --region ap-northeast-2
```

### 문제 4: 네트워크 연결 실패
```bash
# Security Group 확인
aws ec2 describe-security-groups \
  --group-ids sg-xxx \
  --region ap-northeast-2

# 서브넷 확인
aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=vpc-07a289adc49898e52" \
  --region ap-northeast-2
```

---

## 🔄 업데이트 및 재배포

### 코드 변경 후 재배포
```bash
# 1. Docker 이미지 재빌드
docker build -f Dockerfile.scanner -t crypto-backtest-scanner:latest .
docker build -f Dockerfile.analyzer -t crypto-backtest-analyzer:latest .

# 2. ECR에 푸시
docker tag crypto-backtest-scanner:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-scanner:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-scanner:latest

docker tag crypto-backtest-analyzer:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-analyzer:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-analyzer:latest

# 3. ECS Service 업데이트 (Analyzer)
aws ecs update-service \
  --cluster crypto-backtest-cluster \
  --service crypto-backtest-analyzer \
  --force-new-deployment \
  --region ap-northeast-2

# 4. Scanner는 다음 스케줄에 자동 반영
```

### Terraform 설정 변경
```bash
cd infrastructure/terraform

# 변경 사항 확인
terraform plan

# 적용
terraform apply
```

---

## 💰 비용 예상

### 월간 비용 (예상)
- **ECS Fargate**
  - Scanner: 1시간마다 5분 실행 = 120분/일 = $0.50/일 = $15/월
  - Analyzer: 평균 3개 컨테이너 24시간 = $90/월
  
- **Amazon MQ (RabbitMQ)**
  - mq.t3.micro: $18/월
  
- **DynamoDB**
  - On-Demand: 쓰기 150회/시간, 읽기 300회/시간 = $5/월
  
- **CloudWatch Logs**
  - 10GB/월 = $5/월
  
- **데이터 전송**
  - Bybit API 호출 = $2/월

**총 예상 비용: ~$135/월**

### 비용 절감 방법
1. Analyzer를 Spot Instance로 변경 (70% 절감)
2. RabbitMQ를 EC2 자체 호스팅 (50% 절감)
3. DynamoDB Provisioned 모드 (30% 절감)
4. 스캔 주기를 2시간으로 변경 (50% 절감)

---

## 🗑️ 리소스 삭제

### 전체 인프라 삭제
```bash
cd infrastructure/terraform

# 삭제 계획 확인
terraform plan -destroy

# 삭제 실행
terraform destroy

# 확인 후 'yes' 입력
```

### ECR 이미지 삭제
```bash
aws ecr delete-repository \
  --repository-name crypto-backtest-scanner \
  --force \
  --region ap-northeast-2

aws ecr delete-repository \
  --repository-name crypto-backtest-analyzer \
  --force \
  --region ap-northeast-2
```

### Secrets Manager 삭제
```bash
aws secretsmanager delete-secret \
  --secret-id crypto-backtest/bybit-api-key \
  --force-delete-without-recovery \
  --region ap-northeast-2

aws secretsmanager delete-secret \
  --secret-id crypto-backtest/bybit-api-secret \
  --force-delete-without-recovery \
  --region ap-northeast-2
```

---

## 📚 참고 자료

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Amazon MQ Documentation](https://docs.aws.amazon.com/amazon-mq/)
- [DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

## 🆘 지원

문제가 발생하면:
1. CloudWatch Logs 확인
2. ECS Task 상태 확인
3. Security Group 규칙 확인
4. IAM 권한 확인
