#!/bin/bash

set -e

echo "=================================="
echo "Redis + Discovery + Scanner 배포"
echo "=================================="
echo ""

# 환경 변수 확인
if [ -f .env ]; then
    source .env
else
    echo "❌ .env 파일이 없습니다"
    exit 1
fi

AWS_REGION=${AWS_REGION:-ap-northeast-2}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="crypto-backtest"

echo "📋 배포 정보:"
echo "  • AWS Region: $AWS_REGION"
echo "  • AWS Account: $AWS_ACCOUNT_ID"
echo "  • Project: $PROJECT_NAME"
echo ""

# ECR 로그인
echo "🔐 ECR 로그인..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# ECR 리포지토리 생성 (없으면)
echo ""
echo "📦 ECR 리포지토리 확인..."

for repo in discovery scanner-v2; do
    if ! aws ecr describe-repositories --repository-names $PROJECT_NAME-$repo --region $AWS_REGION 2>/dev/null; then
        echo "  • $repo 리포지토리 생성 중..."
        aws ecr create-repository \
            --repository-name $PROJECT_NAME-$repo \
            --region $AWS_REGION \
            --image-scanning-configuration scanOnPush=true
    else
        echo "  • $repo 리포지토리 존재"
    fi
done

# Discovery 이미지 빌드 및 푸시
echo ""
echo "🔨 Discovery 이미지 빌드..."
docker build \
    -t $PROJECT_NAME-discovery:latest \
    -f services/discovery/Dockerfile \
    .

echo "📤 Discovery 이미지 푸시..."
docker tag $PROJECT_NAME-discovery:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME-discovery:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME-discovery:latest

# Scanner V2 이미지 빌드 및 푸시
echo ""
echo "🔨 Scanner V2 이미지 빌드..."
docker build \
    -t $PROJECT_NAME-scanner-v2:latest \
    -f services/scanner/Dockerfile \
    .

echo "📤 Scanner V2 이미지 푸시..."
docker tag $PROJECT_NAME-scanner-v2:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME-scanner-v2:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME-scanner-v2:latest

# Terraform 적용
echo ""
echo "🏗️  Terraform 적용..."
cd infrastructure/terraform

terraform init
terraform plan -out=tfplan
terraform apply tfplan

cd ../..

# ECS 서비스 업데이트
echo ""
echo "🔄 ECS 서비스 업데이트..."

# Discovery 서비스 업데이트
echo "  • Discovery 서비스 업데이트..."
aws ecs update-service \
    --cluster $PROJECT_NAME-cluster \
    --service $PROJECT_NAME-discovery \
    --force-new-deployment \
    --region $AWS_REGION \
    > /dev/null

# Scanner V2 서비스 업데이트
echo "  • Scanner V2 서비스 업데이트..."
aws ecs update-service \
    --cluster $PROJECT_NAME-cluster \
    --service $PROJECT_NAME-scanner-v2 \
    --force-new-deployment \
    --region $AWS_REGION \
    > /dev/null

echo ""
echo "=================================="
echo "✅ 배포 완료!"
echo "=================================="
echo ""
echo "📊 서비스 상태 확인:"
echo "  aws ecs describe-services \\"
echo "    --cluster $PROJECT_NAME-cluster \\"
echo "    --services $PROJECT_NAME-discovery $PROJECT_NAME-scanner-v2 \\"
echo "    --region $AWS_REGION"
echo ""
echo "📝 로그 확인:"
echo "  • Discovery: aws logs tail /ecs/$PROJECT_NAME-discovery --follow"
echo "  • Scanner V2: aws logs tail /ecs/$PROJECT_NAME-scanner-v2 --follow"
echo ""
echo "🔍 Redis 확인:"
echo "  # Redis 엔드포인트 조회"
echo "  terraform output redis_endpoint"
echo ""
