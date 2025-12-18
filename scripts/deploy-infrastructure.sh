#!/bin/bash
# Terraform 인프라 배포 스크립트

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Terraform 인프라 배포${NC}"
echo -e "${BLUE}========================================${NC}"

cd infrastructure/terraform

echo -e "\n${GREEN}1. Terraform 초기화...${NC}"
terraform init

echo -e "\n${GREEN}2. Terraform 계획 확인...${NC}"
terraform plan

echo -e "\n${GREEN}3. Terraform 적용...${NC}"
terraform apply -auto-approve

echo -e "\n${GREEN}4. 출력 값 확인...${NC}"
terraform output

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 인프라 배포 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
