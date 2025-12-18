#!/bin/bash
# ECS 배포 자동화 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 설정
AWS_REGION="ap-northeast-2"
VPC_ID="vpc-07a289adc49898e52"
PROJECT_NAME="crypto-backtest"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Crypto Backtest ECS 배포 스크립트${NC}"
echo -e "${GREEN}========================================${NC}\n"

# AWS Account ID 가져오기
echo -e "${YELLOW}[1/8] AWS Account ID 확인...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ Account ID: ${AWS_ACCOUNT_ID}${NC}\n"

# ECR 리포지토리 생성
echo -e "${YELLOW}[2/8] ECR 리포지토리 생성...${NC}"
aws ecr describe-repositories --repository-names ${PROJECT_NAME}-scanner --region ${AWS_REGION} 2>/dev/null || \
  aws ecr create-repository --repository-name ${PROJECT_NAME}-scanner --region ${AWS_REGION}

aws ecr describe-repositories --repository-names ${PROJECT_NAME}-analyzer --region ${AWS_REGION} 2>/dev/null || \
  aws ecr create-repository --repository-name ${PROJECT_NAME}-analyzer --region ${AWS_REGION}

echo -e "${GREEN}✓ ECR 리포지토리 준비 완료${NC}\n"

# ECR 로그인
echo -e "${YELLOW}[3/8] ECR 로그인...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
echo -e "${GREEN}✓ ECR 로그인 완료${NC}\n"

# Docker 이미지 빌드
echo -e "${YELLOW}[4/8] Docker 이미지 빌드...${NC}"
echo "  - Scanner 이미지 빌드 중..."
docker build -f Dockerfile.scanner -t ${PROJECT_NAME}-scanner:latest . --quiet

echo "  - Analyzer 이미지 빌드 중..."
docker build -f Dockerfile.analyzer -t ${PROJECT_NAME}-analyzer:latest . --quiet

echo -e "${GREEN}✓ Docker 이미지 빌드 완료${NC}\n"

# Docker 이미지 태그 및 푸시
echo -e "${YELLOW}[5/8] Docker 이미지 푸시...${NC}"
echo "  - Scanner 이미지 푸시 중..."
docker tag ${PROJECT_NAME}-scanner:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-scanner:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-scanner:latest

echo "  - Analyzer 이미지 푸시 중..."
docker tag ${PROJECT_NAME}-analyzer:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-analyzer:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-analyzer:latest

echo -e "${GREEN}✓ Docker 이미지 푸시 완료${NC}\n"

# Secrets Manager 확인
echo -e "${YELLOW}[6/8] Secrets Manager 확인...${NC}"
if ! aws secretsmanager describe-secret --secret-id ${PROJECT_NAME}/bybit-api-key --region ${AWS_REGION} 2>/dev/null; then
  echo -e "${RED}⚠️  Bybit API 키가 설정되지 않았습니다.${NC}"
  echo -e "${YELLOW}다음 명령어로 설정하세요:${NC}"
  echo "  aws secretsmanager create-secret --name ${PROJECT_NAME}/bybit-api-key --secret-string \"YOUR_KEY\" --region ${AWS_REGION}"
  echo "  aws secretsmanager create-secret --name ${PROJECT_NAME}/bybit-api-secret --secret-string \"YOUR_SECRET\" --region ${AWS_REGION}"
  echo ""
  read -p "계속하시겠습니까? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
else
  echo -e "${GREEN}✓ Secrets Manager 설정 확인 완료${NC}\n"
fi

# Terraform 초기화 및 배포
echo -e "${YELLOW}[7/8] Terraform 인프라 배포...${NC}"
cd infrastructure/terraform

if [ ! -d ".terraform" ]; then
  echo "  - Terraform 초기화 중..."
  terraform init
fi

echo "  - Terraform 계획 생성 중..."
terraform plan -out=tfplan

echo ""
read -p "배포를 진행하시겠습니까? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "  - Terraform 배포 중..."
  terraform apply tfplan
  echo -e "${GREEN}✓ Terraform 배포 완료${NC}\n"
else
  echo -e "${YELLOW}배포가 취소되었습니다.${NC}"
  exit 0
fi

cd ../..

# 배포 확인
echo -e "${YELLOW}[8/8] 배포 확인...${NC}"
echo "  - ECS 클러스터 확인 중..."
aws ecs describe-clusters --clusters ${PROJECT_NAME}-cluster --region ${AWS_REGION} --query 'clusters[0].status' --output text

echo "  - DynamoDB 테이블 확인 중..."
aws dynamodb describe-table --table-name ${PROJECT_NAME}-results --region ${AWS_REGION} --query 'Table.TableStatus' --output text

echo -e "${GREEN}✓ 배포 확인 완료${NC}\n"

# 완료 메시지
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 배포가 완료되었습니다!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}다음 단계:${NC}"
echo "1. Scanner 수동 실행 (테스트):"
echo "   aws ecs run-task --cluster ${PROJECT_NAME}-cluster --task-definition ${PROJECT_NAME}-scanner --launch-type FARGATE --region ${AWS_REGION}"
echo ""
echo "2. 로그 확인:"
echo "   aws logs tail /ecs/${PROJECT_NAME}-scanner --follow --region ${AWS_REGION}"
echo "   aws logs tail /ecs/${PROJECT_NAME}-analyzer --follow --region ${AWS_REGION}"
echo ""
echo "3. DynamoDB 데이터 확인:"
echo "   aws dynamodb scan --table-name ${PROJECT_NAME}-results --region ${AWS_REGION} --max-items 5"
echo ""
echo -e "${GREEN}배포 가이드: DEPLOYMENT_GUIDE.md${NC}"
