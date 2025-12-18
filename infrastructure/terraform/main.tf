# Crypto Backtest Infrastructure
# ECS + RabbitMQ + DynamoDB

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ===== Variables =====
variable "aws_region" {
  default = "ap-northeast-2"
}

variable "vpc_id" {
  description = "Existing VPC ID"
  default     = "vpc-07a289adc49898e52"
}

variable "project_name" {
  default = "crypto-backtest"
}

variable "environment" {
  default = "production"
}

# ===== VPC (기존 VPC 사용) =====
data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  
  filter {
    name   = "tag:Name"
    values = ["*private*"]  # private 서브넷 선택
  }
}

# Public 서브넷도 가져오기 (Fargate는 public IP 필요)
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  
  filter {
    name   = "tag:Name"
    values = ["*public*"]  # public 서브넷 선택
  }
}

# ===== Security Groups =====
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-tasks"
  description = "Security group for ECS tasks"
  vpc_id      = data.aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-ecs-tasks"
    Environment = var.environment
  }
}

resource "aws_security_group" "rabbitmq" {
  name        = "${var.project_name}-rabbitmq"
  description = "Security group for RabbitMQ"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    from_port       = 5671
    to_port         = 5671
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  ingress {
    from_port       = 15671
    to_port         = 15671
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-rabbitmq"
    Environment = var.environment
  }
}

# ===== Amazon MQ (RabbitMQ) =====
resource "aws_mq_broker" "rabbitmq" {
  broker_name              = "${var.project_name}-rabbitmq"
  engine_type              = "RabbitMQ"
  engine_version           = "3.13"
  host_instance_type       = "mq.t3.micro"  # 개발: t3.micro, 프로덕션: m5.large
  deployment_mode          = "SINGLE_INSTANCE"  # 프로덕션: CLUSTER_MULTI_AZ
  auto_minor_version_upgrade = true

  user {
    username = "admin"
    password = random_password.rabbitmq_password.result
  }

  subnet_ids         = length(data.aws_subnets.public.ids) > 0 ? [data.aws_subnets.public.ids[0]] : [data.aws_subnets.private.ids[0]]
  # security_groups cannot be specified when publicly_accessible = true
  # security_groups    = [aws_security_group.rabbitmq.id]
  publicly_accessible = true

  logs {
    general = true
  }

  tags = {
    Name        = "${var.project_name}-rabbitmq"
    Environment = var.environment
  }
}

resource "random_password" "rabbitmq_password" {
  length  = 16
  special = true
  override_special = "!#$%&*()-_+<>?"  # RabbitMQ에서 허용하는 특수문자만 사용 (,:= 제외)
}

# ===== DynamoDB Tables =====
resource "aws_dynamodb_table" "backtest_results" {
  name           = "${var.project_name}-results"
  billing_mode   = "PAY_PER_REQUEST"  # 또는 PROVISIONED
  hash_key       = "symbol"
  range_key      = "scan_timestamp"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "scan_timestamp"
    type = "N"
  }

  attribute {
    name = "scan_id"
    type = "S"
  }

  attribute {
    name = "optimal_pnl"
    type = "N"
  }

  attribute {
    name = "optimal_timeframe"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # GSI-1: ScanIdIndex
  global_secondary_index {
    name            = "ScanIdIndex"
    hash_key        = "scan_id"
    range_key       = "optimal_pnl"
    projection_type = "ALL"
  }

  # GSI-2: OptimalTimeframeIndex
  global_secondary_index {
    name            = "OptimalTimeframeIndex"
    hash_key        = "optimal_timeframe"
    range_key       = "optimal_pnl"
    projection_type = "ALL"
  }

  # GSI-3: StatusIndex
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "scan_timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-results"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "scan_history" {
  name         = "${var.project_name}-scan-history"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "scan_id"

  attribute {
    name = "scan_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-scan-history"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "trading_positions" {
  name         = "${var.project_name}-trading-positions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "symbol"
  range_key    = "signal_timestamp"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "signal_timestamp"
    type = "N"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "confidence"
    type = "N"
  }

  # GSI-1: StatusIndex
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "signal_timestamp"
    projection_type = "ALL"
  }

  # GSI-2: ConfidenceIndex
  global_secondary_index {
    name            = "ConfidenceIndex"
    hash_key        = "status"
    range_key       = "confidence"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-trading-positions"
    Environment = var.environment
  }
}

# ===== IAM Roles =====
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Secrets Manager 접근 권한 추가
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${var.project_name}-ecs-task-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.project_name}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.backtest_results.arn,
          "${aws_dynamodb_table.backtest_results.arn}/index/*",
          aws_dynamodb_table.scan_history.arn,
          aws_dynamodb_table.trading_positions.arn,
          "${aws_dynamodb_table.trading_positions.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/*"
      }
    ]
  })
}

# ===== ECS Cluster =====
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-cluster"
    Environment = var.environment
  }
}

# ===== CloudWatch Log Groups =====
resource "aws_cloudwatch_log_group" "scanner" {
  name              = "/ecs/${var.project_name}-scanner"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-scanner-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "analyzer" {
  name              = "/ecs/${var.project_name}-analyzer"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-analyzer-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "selector" {
  name              = "/ecs/${var.project_name}-selector"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-selector-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "finder" {
  name              = "/ecs/${var.project_name}-finder"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-finder-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "executor" {
  name              = "/ecs/${var.project_name}-executor"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-executor-logs"
    Environment = var.environment
  }
}

# ===== EventBridge Rules =====
# Scanner: 1시간마다
resource "aws_cloudwatch_event_rule" "scanner_schedule" {
  name                = "${var.project_name}-scanner-schedule"
  description         = "Run scanner every hour"
  schedule_expression = "rate(1 hour)"

  tags = {
    Name        = "${var.project_name}-scanner-schedule"
    Environment = var.environment
  }
}

# Strategy Selector: 1분마다
resource "aws_cloudwatch_event_rule" "selector_schedule" {
  name                = "${var.project_name}-selector-schedule"
  description         = "Run strategy selector every minute"
  schedule_expression = "rate(1 minute)"

  tags = {
    Name        = "${var.project_name}-selector-schedule"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "scanner" {
  rule      = aws_cloudwatch_event_rule.scanner_schedule.name
  target_id = "scanner-task"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.eventbridge_ecs.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.scanner.arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = length(data.aws_subnets.public.ids) > 0 ? data.aws_subnets.public.ids : data.aws_subnets.private.ids
      security_groups  = [aws_security_group.ecs_tasks.id]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "selector" {
  rule      = aws_cloudwatch_event_rule.selector_schedule.name
  target_id = "selector-task"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.eventbridge_ecs.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.selector.arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = length(data.aws_subnets.public.ids) > 0 ? data.aws_subnets.public.ids : data.aws_subnets.private.ids
      security_groups  = [aws_security_group.ecs_tasks.id]
      assign_public_ip = true
    }
  }
}

resource "aws_iam_role" "eventbridge_ecs" {
  name = "${var.project_name}-eventbridge-ecs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_ecs" {
  name = "${var.project_name}-eventbridge-ecs-policy"
  role = aws_iam_role.eventbridge_ecs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecs:RunTask"
      ]
      Resource = [
        aws_ecs_task_definition.scanner.arn,
        aws_ecs_task_definition.selector.arn
      ]
    },
    {
      Effect = "Allow"
      Action = [
        "iam:PassRole"
      ]
      Resource = [
        aws_iam_role.ecs_task_execution.arn,
        aws_iam_role.ecs_task.arn
      ]
    }]
  })
}

# ===== ECS Task Definitions =====
resource "aws_ecs_task_definition" "scanner" {
  family                   = "${var.project_name}-scanner"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "scanner"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-scanner:latest"
    essential = true

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.scanner.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "scanner"
      }
    }

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_TABLE", value = aws_dynamodb_table.backtest_results.name },
      { name = "DYNAMODB_HISTORY_TABLE", value = aws_dynamodb_table.scan_history.name },
      { name = "RABBITMQ_HOST", value = split(":", split("://", aws_mq_broker.rabbitmq.instances[0].endpoints[0])[1])[0] },
      { name = "RABBITMQ_PORT", value = "5671" },
      { name = "RABBITMQ_USER", value = "admin" },
      { name = "RABBITMQ_PASS", value = random_password.rabbitmq_password.result },
      { name = "RABBITMQ_QUEUE", value = "backtest-tasks" }
    ],
    
    secrets = [
      {
        name      = "BYBIT_API_KEY"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_key.arn
      },
      {
        name      = "BYBIT_API_SECRET"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_secret.arn
      },
      {
        name      = "BYBIT_TESTNET"
        valueFrom = data.aws_secretsmanager_secret.bybit_testnet.arn
      }
    ]
  }])
}

resource "aws_ecs_task_definition" "analyzer" {
  family                   = "${var.project_name}-analyzer"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "analyzer"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-analyzer:latest"
    essential = true

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.analyzer.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "analyzer"
      }
    }

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_TABLE", value = aws_dynamodb_table.backtest_results.name },
      { name = "DYNAMODB_HISTORY_TABLE", value = aws_dynamodb_table.scan_history.name },
      { name = "RABBITMQ_HOST", value = split(":", split("://", aws_mq_broker.rabbitmq.instances[0].endpoints[0])[1])[0] },
      { name = "RABBITMQ_PORT", value = "5671" },
      { name = "RABBITMQ_USER", value = "admin" },
      { name = "RABBITMQ_PASS", value = random_password.rabbitmq_password.result },
      { name = "RABBITMQ_QUEUE", value = "backtest-tasks" },
      { name = "PREFETCH_COUNT", value = "1" }
    ],
    
    secrets = [
      {
        name      = "BYBIT_API_KEY"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_key.arn
      },
      {
        name      = "BYBIT_API_SECRET"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_secret.arn
      },
      {
        name      = "BYBIT_TESTNET"
        valueFrom = data.aws_secretsmanager_secret.bybit_testnet.arn
      }
    ]
  }])
}

# Strategy Selector Task Definition
resource "aws_ecs_task_definition" "selector" {
  family                   = "${var.project_name}-selector"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "selector"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-selector:latest"
    essential = true

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.selector.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "selector"
      }
    }

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_TABLE", value = aws_dynamodb_table.backtest_results.name },
      { name = "RABBITMQ_HOST", value = split(":", split("://", aws_mq_broker.rabbitmq.instances[0].endpoints[0])[1])[0] },
      { name = "RABBITMQ_PORT", value = "5671" },
      { name = "RABBITMQ_USER", value = "admin" },
      { name = "RABBITMQ_PASS", value = random_password.rabbitmq_password.result },
      { name = "RABBITMQ_TRADING_QUEUE", value = "trading-signals" },
      { name = "MIN_WIN_RATE", value = "40.0" },
      { name = "MIN_PNL", value = "50.0" },
      { name = "MIN_TRADES", value = "10" }
    ]
  }])
}

# Position Finder Task Definition
resource "aws_ecs_task_definition" "finder" {
  family                   = "${var.project_name}-finder"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "finder"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-finder:latest"
    essential = true

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.finder.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "finder"
      }
    }

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_POSITIONS_TABLE", value = aws_dynamodb_table.trading_positions.name },
      { name = "RABBITMQ_HOST", value = split(":", split("://", aws_mq_broker.rabbitmq.instances[0].endpoints[0])[1])[0] },
      { name = "RABBITMQ_PORT", value = "5671" },
      { name = "RABBITMQ_USER", value = "admin" },
      { name = "RABBITMQ_PASS", value = random_password.rabbitmq_password.result },
      { name = "RABBITMQ_TRADING_QUEUE", value = "trading-signals" },
      { name = "PREFETCH_COUNT", value = "1" }
    ],
    
    secrets = [
      {
        name      = "BYBIT_API_KEY"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_key.arn
      },
      {
        name      = "BYBIT_API_SECRET"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_secret.arn
      },
      {
        name      = "BYBIT_TESTNET"
        valueFrom = data.aws_secretsmanager_secret.bybit_testnet.arn
      }
    ]
  }])
}

# Order Executor Task Definition
resource "aws_ecs_task_definition" "executor" {
  family                   = "${var.project_name}-executor"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "executor"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-executor:latest"
    essential = true

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.executor.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "executor"
      }
    }

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_POSITIONS_TABLE", value = aws_dynamodb_table.trading_positions.name },
      { name = "POSITION_SIZE", value = "100.0" },
      { name = "LEVERAGE", value = "10" },
      { name = "SCAN_INTERVAL", value = "5" }
    ],
    
    secrets = [
      {
        name      = "BYBIT_API_KEY"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_key.arn
      },
      {
        name      = "BYBIT_API_SECRET"
        valueFrom = data.aws_secretsmanager_secret.bybit_api_secret.arn
      },
      {
        name      = "BYBIT_TESTNET"
        valueFrom = data.aws_secretsmanager_secret.bybit_testnet.arn
      }
    ]
  }])
}

# ===== ECS Services =====
# Analyzer Service (Auto-scaling 1-10)
resource "aws_ecs_service" "analyzer" {
  name            = "${var.project_name}-analyzer"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.analyzer.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = length(data.aws_subnets.public.ids) > 0 ? data.aws_subnets.public.ids : data.aws_subnets.private.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
}

# Position Finder Service (Auto-scaling 1-5)
resource "aws_ecs_service" "finder" {
  name            = "${var.project_name}-finder"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.finder.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = length(data.aws_subnets.public.ids) > 0 ? data.aws_subnets.public.ids : data.aws_subnets.private.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
}

# Order Executor Service (1개 고정)
resource "aws_ecs_service" "executor" {
  name            = "${var.project_name}-executor"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.executor.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = length(data.aws_subnets.public.ids) > 0 ? data.aws_subnets.public.ids : data.aws_subnets.private.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
}

# ===== Auto Scaling =====
# Analyzer Auto Scaling (1-10)
resource "aws_appautoscaling_target" "analyzer" {
  max_capacity       = 10
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.analyzer.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "analyzer_cpu" {
  name               = "${var.project_name}-analyzer-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.analyzer.resource_id
  scalable_dimension = aws_appautoscaling_target.analyzer.scalable_dimension
  service_namespace  = aws_appautoscaling_target.analyzer.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# Position Finder Auto Scaling (1-5)
resource "aws_appautoscaling_target" "finder" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.finder.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "finder_cpu" {
  name               = "${var.project_name}-finder-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.finder.resource_id
  scalable_dimension = aws_appautoscaling_target.finder.scalable_dimension
  service_namespace  = aws_appautoscaling_target.finder.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# ===== Data Sources =====
data "aws_caller_identity" "current" {}

# Secrets Manager Secrets
data "aws_secretsmanager_secret" "bybit_api_key" {
  name = "${var.project_name}/bybit-api-key"
}

data "aws_secretsmanager_secret" "bybit_api_secret" {
  name = "${var.project_name}/bybit-api-secret"
}

data "aws_secretsmanager_secret" "bybit_testnet" {
  name = "${var.project_name}/bybit-testnet"
}

# ===== Outputs =====
output "rabbitmq_endpoint" {
  value = aws_mq_broker.rabbitmq.instances[0].endpoints[0]
}

output "dynamodb_results_table" {
  value = aws_dynamodb_table.backtest_results.name
}

output "dynamodb_history_table" {
  value = aws_dynamodb_table.scan_history.name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "dynamodb_positions_table" {
  value = aws_dynamodb_table.trading_positions.name
}

output "rabbitmq_password" {
  value     = random_password.rabbitmq_password.result
  sensitive = true
}
