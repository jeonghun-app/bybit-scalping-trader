#!/bin/bash
# ECS 서비스 업데이트 스크립트

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

CLUSTER_NAME="crypto-backtest-cluster"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ECS 서비스 업데이트${NC}"
echo -e "${BLUE}========================================${NC}"

# 서비스 목록 (스케줄 태스크 제외)
SERVICES=("analyzer" "finder" "executor")

for SERVICE in "${SERVICES[@]}"; do
    echo -e "\n${GREEN}${SERVICE} 서비스 업데이트...${NC}"
    aws ecs update-service \
        --cluster ${CLUSTER_NAME} \
        --service crypto-backtest-${SERVICE} \
        --force-new-deployment \
        --query 'service.serviceName' \
        --output text
    echo -e "${GREEN}✅ ${SERVICE} 업데이트 완료${NC}"
done

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 모든 서비스 업데이트 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
