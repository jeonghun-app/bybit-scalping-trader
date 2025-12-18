#!/bin/bash
# Docker 이미지 빌드 및 ECR 푸시 스크립트

set -e

# 설정
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID="081041735764"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# 색상 출력
GREEN='\033[0.32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker 이미지 빌드 및 ECR 푸시${NC}"
echo -e "${BLUE}========================================${NC}"

# ECR 로그인
echo -e "\n${GREEN}1. ECR 로그인...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}

# 서비스 목록
SERVICES=("scanner" "analyzer" "selector" "finder" "executor")

# 각 서비스 빌드 및 푸시
for SERVICE in "${SERVICES[@]}"; do
    echo -e "\n${GREEN}2. ${SERVICE} 이미지 빌드...${NC}"
    docker build \
        -f services/${SERVICE}/Dockerfile \
        -t ${ECR_REGISTRY}/crypto-backtest-${SERVICE}:latest \
        .
    
    echo -e "${GREEN}3. ${SERVICE} 이미지 푸시...${NC}"
    docker push ${ECR_REGISTRY}/crypto-backtest-${SERVICE}:latest
    
    echo -e "${GREEN}✅ ${SERVICE} 완료${NC}"
done

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 모든 이미지 빌드 및 푸시 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
