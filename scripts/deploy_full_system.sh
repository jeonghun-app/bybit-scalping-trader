#!/bin/bash
# 전체 시스템 자동 배포 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
AWS_REGION="ap-northeast-2"
VPC_ID="vpc-07a289adc49898e52"
PROJECT_NAME="crypto-backtest"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Crypto Trading System 전체 배포${NC}"
echo -e "${BLUE}========================================${NC}\n"

# AWS Account ID 가져오기
echo -e "${YELLOW}[1/10] AWS Account ID 확인...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ Account ID: ${AWS_ACCOUNT_ID}${NC}\n"

# ECR 리포지토리 생성
echo -e "${YELLOW}[2/10] ECR 리포지토리 생성...${NC}"
for repo in scanner analyzer selector finder executor; do
  aws ecr describe-repositories --repository-names ${PROJECT_NAME}-${repo} --region ${AWS_REGION} 2>/dev/null || \
    aws ecr create-repository --repository-name ${PROJECT_NAME}-${repo} --region ${AWS_REGION} > /dev/null
  echo -e "  ✓ ${PROJECT_NAME}-${repo}"
done
echo -e "${GREEN}✓ ECR 리포지토리 준비 완료${NC}\n"

# ECR 로그인
echo -e "${YELLOW}[3/10] ECR 로그인...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
echo -e "${GREEN}✓ ECR 로그인 완료${NC}\n"

# Docker 이미지 빌드
echo -e "${YELLOW}[4/10] Docker 이미지 빌드...${NC}"
echo "  - Scanner 이미지 빌드 중..."
docker build -f Dockerfile.scanner -t ${PROJECT_NAME}-scanner:latest . --quiet

echo "  - Analyzer 이미지 빌드 중..."
docker build -f Dockerfile.analyzer -t ${PROJECT_NAME}-analyzer:latest . --quiet

echo "  - Selector 이미지 빌드 중..."
docker build -f Dockerfile.selector -t ${PROJECT_NAME}-selector:latest . --quiet

echo "  - Finder 이미지 빌드 중..."
docker build -f Dockerfile.finder -t ${PROJECT_NAME}-finder:latest . --quiet

echo "  - Executor 이미지 빌드 중..."
docker build -f Dockerfile.executor -t ${PROJECT_NAME}-executor:latest . --quiet

echo -e "${GREEN}✓ Docker 이미지 빌드 완료${NC}\n"

# Docker 이미지 푸시
echo -e "${YELLOW}[5/10] Docker 이미지 푸시...${NC}"
for service in scanner analyzer selector finder executor; do
  echo "  - ${service} 이미지 푸시 중..."
  docker tag ${PROJECT_NAME}-${service}:latest \
    ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-${service}:latest
  docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-${service}:latest > /dev/null
done
echo -e "${GREEN}✓ Docker 이미지 푸시 완료${NC}\n"

# Secrets Manager 확인
echo -e "${YELLOW}[6/10] Secrets Manager 확인...${NC}"
secrets_ok=true
for secret in bybit-api-key bybit-api-secret bybit-testnet; do
  if aws secretsmanager describe-secret --secret-id ${PROJECT_NAME}/${secret} --region ${AWS_REGION} 2>/dev/null > /dev/null; then
    echo -e "  ✓ ${PROJECT_NAME}/${secret}"
  else
    echo -e "  ${RED}✗ ${PROJECT_NAME}/${secret} 없음${NC}"
    secrets_ok=false
  fi
done

if [ "$secrets_ok" = false ]; then
  echo -e "${RED}⚠️  일부 Secrets가 설정되지 않았습니다.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Secrets Manager 확인 완료${NC}\n"

# Terraform 초기화
echo -e "${YELLOW}[7/10] Terraform 초기화...${NC}"
cd infrastructure/terraform

if [ ! -d ".terraform" ]; then
  terraform init
fi
echo -e "${GREEN}✓ Terraform 초기화 완료${NC}\n"

# Terraform 계획
echo -e "${YELLOW}[8/10] Terraform 계획 생성...${NC}"
terraform plan -out=tfplan
echo -e "${GREEN}✓ Terraform 계획 생성 완료${NC}\n"

# Terraform 배포
echo -e "${YELLOW}[9/10] Terraform 배포...${NC}"
echo ""
read -p "배포를 진행하시겠습니까? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  terraform apply tfplan
  echo -e "${GREEN}✓ Terraform 배포 완료${NC}\n"
else
  echo -e "${YELLOW}배포가 취소되었습니다.${NC}"
  exit 0
fi

cd ../..

# 배포 확인
echo -e "${YELLOW}[10/10] 배포 확인...${NC}"

echo "  - ECS 클러스터 확인..."
CLUSTER_STATUS=$(aws ecs describe-clusters --clusters ${PROJECT_NAME}-cluster --region ${AWS_REGION} --query 'clusters[0].status' --output text)
echo "    ✓ 클러스터 상태: ${CLUSTER_STATUS}"

echo "  - DynamoDB 테이블 확인..."
for table in results scan-history trading-positions; do
  TABLE_STATUS=$(aws dynamodb describe-table --table-name ${PROJECT_NAME}-${table} --region ${AWS_REGION} --query 'Table.TableStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  if [ "$TABLE_STATUS" = "ACTIVE" ]; then
    echo "    ✓ ${PROJECT_NAME}-${table}: ${TABLE_STATUS}"
  else
    echo "    ⚠️  ${PROJECT_NAME}-${table}: ${TABLE_STATUS}"
  fi
done

echo "  - RabbitMQ 확인..."
BROKER_COUNT=$(aws mq list-brokers --region ${AWS_REGION} --query "BrokerSummaries[?BrokerName=='${PROJECT_NAME}-rabbitmq'].BrokerName" --output text | wc -l)
if [ $BROKER_COUNT -gt 0 ]; then
  echo "    ✓ RabbitMQ 브로커 존재"
else
  echo "    ⚠️  RabbitMQ 브로커 없음"
fi

echo -e "${GREEN}✓ 배포 확인 완료${NC}\n"

# 완료 메시지
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 전체 배포가 완료되었습니다!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${BLUE}📊 배포된 서비스:${NC}"
echo "  1. Scanner Service (1시간마다)"
echo "  2. Analyzer Service (Auto-scaling 1-10)"
echo "  3. Strategy Selector Service (1분마다)"
echo "  4. Position Finder Service (Auto-scaling 1-5)"
echo "  5. Order Executor Service (5초마다)"
echo ""

echo -e "${BLUE}📋 다음 단계:${NC}"
echo "1. Scanner 수동 실행 (테스트):"
echo "   ./test_scanner.sh"
echo ""
echo "2. 로그 확인:"
echo "   aws logs tail /ecs/${PROJECT_NAME}-scanner --follow --region ${AWS_REGION}"
echo "   aws logs tail /ecs/${PROJECT_NAME}-analyzer --follow --region ${AWS_REGION}"
echo "   aws logs tail /ecs/${PROJECT_NAME}-selector --follow --region ${AWS_REGION}"
echo "   aws logs tail /ecs/${PROJECT_NAME}-finder --follow --region ${AWS_REGION}"
echo "   aws logs tail /ecs/${PROJECT_NAME}-executor --follow --region ${AWS_REGION}"
echo ""
echo "3. DynamoDB 데이터 확인:"
echo "   aws dynamodb scan --table-name ${PROJECT_NAME}-results --max-items 5 --region ${AWS_REGION}"
echo "   aws dynamodb scan --table-name ${PROJECT_NAME}-trading-positions --max-items 5 --region ${AWS_REGION}"
echo ""
echo -e "${GREEN}배포 가이드: DEPLOYMENT_GUIDE.md${NC}"
echo -e "${GREEN}트레이딩 가이드: TRADING_SYSTEM_GUIDE.md${NC}"
echo -e "${GREEN}주문 실행 가이드: ORDER_EXECUTION_GUIDE.md${NC}"
