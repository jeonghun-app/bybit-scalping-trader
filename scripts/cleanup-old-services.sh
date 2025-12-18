#!/bin/bash

set -e

echo "=================================="
echo "기존 ECS 서비스 정리"
echo "=================================="
echo ""

# 환경 변수
AWS_REGION=${AWS_REGION:-ap-northeast-2}
PROJECT_NAME="crypto-backtest"
CLUSTER_NAME="${PROJECT_NAME}-cluster"

echo "📋 정리 대상:"
echo "  • AWS Region: $AWS_REGION"
echo "  • Cluster: $CLUSTER_NAME"
echo ""

# 기존 서비스 목록
OLD_SERVICES=(
    "scanner"
    "analyzer"
    "selector"
    "finder"
    "executor"
)

echo "🔍 기존 서비스 확인 중..."
echo ""

# 각 서비스 확인 및 삭제
for service in "${OLD_SERVICES[@]}"; do
    SERVICE_NAME="${PROJECT_NAME}-${service}"
    
    # 서비스 존재 확인
    if aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $AWS_REGION \
        --query 'services[0].status' \
        --output text 2>/dev/null | grep -q "ACTIVE"; then
        
        echo "🗑️  $SERVICE_NAME 삭제 중..."
        
        # 서비스 desired count를 0으로 설정
        aws ecs update-service \
            --cluster $CLUSTER_NAME \
            --service $SERVICE_NAME \
            --desired-count 0 \
            --region $AWS_REGION \
            > /dev/null 2>&1 || true
        
        # 잠시 대기
        sleep 2
        
        # 서비스 삭제
        aws ecs delete-service \
            --cluster $CLUSTER_NAME \
            --service $SERVICE_NAME \
            --force \
            --region $AWS_REGION \
            > /dev/null 2>&1 || true
        
        echo "   ✅ $SERVICE_NAME 삭제 완료"
    else
        echo "   ⏭️  $SERVICE_NAME 없음 (스킵)"
    fi
done

echo ""
echo "⏳ 서비스 삭제 완료 대기 중 (30초)..."
sleep 30

echo ""
echo "🔍 태스크 정의 확인 중..."
echo ""

# 태스크 정의 비활성화
for service in "${OLD_SERVICES[@]}"; do
    TASK_FAMILY="${PROJECT_NAME}-${service}"
    
    # 활성 태스크 정의 조회
    TASK_ARNS=$(aws ecs list-task-definitions \
        --family-prefix $TASK_FAMILY \
        --status ACTIVE \
        --region $AWS_REGION \
        --query 'taskDefinitionArns[]' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$TASK_ARNS" ]; then
        echo "🗑️  $TASK_FAMILY 태스크 정의 비활성화 중..."
        
        for arn in $TASK_ARNS; do
            aws ecs deregister-task-definition \
                --task-definition $arn \
                --region $AWS_REGION \
                > /dev/null 2>&1 || true
        done
        
        echo "   ✅ $TASK_FAMILY 비활성화 완료"
    else
        echo "   ⏭️  $TASK_FAMILY 없음 (스킵)"
    fi
done

echo ""
echo "🔍 EventBridge 규칙 확인 중..."
echo ""

# EventBridge 규칙 삭제
EVENT_RULES=(
    "${PROJECT_NAME}-scanner-schedule"
    "${PROJECT_NAME}-selector-schedule"
)

for rule in "${EVENT_RULES[@]}"; do
    # 규칙 존재 확인
    if aws events describe-rule \
        --name $rule \
        --region $AWS_REGION \
        > /dev/null 2>&1; then
        
        echo "🗑️  $rule 삭제 중..."
        
        # 타겟 제거
        TARGET_IDS=$(aws events list-targets-by-rule \
            --rule $rule \
            --region $AWS_REGION \
            --query 'Targets[].Id' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$TARGET_IDS" ]; then
            aws events remove-targets \
                --rule $rule \
                --ids $TARGET_IDS \
                --region $AWS_REGION \
                > /dev/null 2>&1 || true
        fi
        
        # 규칙 삭제
        aws events delete-rule \
            --name $rule \
            --region $AWS_REGION \
            > /dev/null 2>&1 || true
        
        echo "   ✅ $rule 삭제 완료"
    else
        echo "   ⏭️  $rule 없음 (스킵)"
    fi
done

echo ""
echo "🔍 CloudWatch 로그 그룹 확인 중..."
echo ""

# CloudWatch 로그 그룹 삭제
LOG_GROUPS=(
    "/ecs/${PROJECT_NAME}-scanner"
    "/ecs/${PROJECT_NAME}-analyzer"
    "/ecs/${PROJECT_NAME}-selector"
    "/ecs/${PROJECT_NAME}-finder"
    "/ecs/${PROJECT_NAME}-executor"
)

for log_group in "${LOG_GROUPS[@]}"; do
    # 로그 그룹 존재 확인
    if aws logs describe-log-groups \
        --log-group-name-prefix $log_group \
        --region $AWS_REGION \
        --query 'logGroups[0].logGroupName' \
        --output text 2>/dev/null | grep -q "$log_group"; then
        
        echo "🗑️  $log_group 삭제 중..."
        
        aws logs delete-log-group \
            --log-group-name $log_group \
            --region $AWS_REGION \
            > /dev/null 2>&1 || true
        
        echo "   ✅ $log_group 삭제 완료"
    else
        echo "   ⏭️  $log_group 없음 (스킵)"
    fi
done

echo ""
echo "🔍 Auto Scaling 설정 확인 중..."
echo ""

# Auto Scaling 타겟 삭제
SCALING_TARGETS=(
    "service/${CLUSTER_NAME}/${PROJECT_NAME}-analyzer"
    "service/${CLUSTER_NAME}/${PROJECT_NAME}-finder"
)

for target in "${SCALING_TARGETS[@]}"; do
    # Auto Scaling 타겟 존재 확인
    if aws application-autoscaling describe-scalable-targets \
        --service-namespace ecs \
        --resource-ids $target \
        --region $AWS_REGION \
        > /dev/null 2>&1; then
        
        echo "🗑️  $target Auto Scaling 삭제 중..."
        
        # 정책 삭제
        POLICY_NAMES=$(aws application-autoscaling describe-scaling-policies \
            --service-namespace ecs \
            --resource-id $target \
            --region $AWS_REGION \
            --query 'ScalingPolicies[].PolicyName' \
            --output text 2>/dev/null || echo "")
        
        for policy in $POLICY_NAMES; do
            aws application-autoscaling delete-scaling-policy \
                --service-namespace ecs \
                --resource-id $target \
                --policy-name $policy \
                --region $AWS_REGION \
                > /dev/null 2>&1 || true
        done
        
        # 타겟 삭제
        aws application-autoscaling deregister-scalable-target \
            --service-namespace ecs \
            --resource-id $target \
            --scalable-dimension ecs:service:DesiredCount \
            --region $AWS_REGION \
            > /dev/null 2>&1 || true
        
        echo "   ✅ $target Auto Scaling 삭제 완료"
    else
        echo "   ⏭️  $target Auto Scaling 없음 (스킵)"
    fi
done

echo ""
echo "🔍 IAM 역할 확인 중..."
echo ""

# EventBridge IAM 역할 삭제
EVENTBRIDGE_ROLE="${PROJECT_NAME}-eventbridge-ecs"

if aws iam get-role --role-name $EVENTBRIDGE_ROLE --region $AWS_REGION > /dev/null 2>&1; then
    echo "🗑️  $EVENTBRIDGE_ROLE IAM 역할 삭제 중..."
    
    # 인라인 정책 삭제
    POLICY_NAMES=$(aws iam list-role-policies \
        --role-name $EVENTBRIDGE_ROLE \
        --query 'PolicyNames[]' \
        --output text 2>/dev/null || echo "")
    
    for policy in $POLICY_NAMES; do
        aws iam delete-role-policy \
            --role-name $EVENTBRIDGE_ROLE \
            --policy-name $policy \
            > /dev/null 2>&1 || true
    done
    
    # 역할 삭제
    aws iam delete-role \
        --role-name $EVENTBRIDGE_ROLE \
        > /dev/null 2>&1 || true
    
    echo "   ✅ $EVENTBRIDGE_ROLE 삭제 완료"
else
    echo "   ⏭️  $EVENTBRIDGE_ROLE 없음 (스킵)"
fi

echo ""
echo "=================================="
echo "✅ 정리 완료!"
echo "=================================="
echo ""
echo "📊 남은 리소스:"
echo "  • ECS Cluster: $CLUSTER_NAME (유지)"
echo "  • RabbitMQ: ${PROJECT_NAME}-rabbitmq (유지)"
echo "  • DynamoDB Tables (유지)"
echo "  • IAM Roles: ecs-task-execution, ecs-task (유지)"
echo ""
echo "🆕 새로운 서비스 배포:"
echo "  ./scripts/deploy-redis-services.sh"
echo ""
