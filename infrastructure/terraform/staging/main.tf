locals {
  name = "fabricassist-${var.environment}"
  public_subnets = {
    for index, zone in var.availability_zones : zone => cidrsubnet(var.vpc_cidr, 4, index)
  }
  private_subnets = {
    for index, zone in var.availability_zones : zone => cidrsubnet(var.vpc_cidr, 4, index + 8)
  }
  common_environment = [
    { name = "FABRICASSIST_ENVIRONMENT", value = "production" },
    { name = "FABRICASSIST_APP_BASE_URL", value = "https://${var.app_hostname}" },
    { name = "FABRICASSIST_API_PUBLIC_URL", value = "https://${var.api_hostname}" },
    { name = "FABRICASSIST_CORS_ALLOWED_ORIGINS", value = "https://${var.app_hostname}" },
    { name = "FABRICASSIST_S3_ENDPOINT_URL", value = "https://s3.${var.aws_region}.amazonaws.com" },
    { name = "FABRICASSIST_S3_PUBLIC_ENDPOINT_URL", value = "https://s3.${var.aws_region}.amazonaws.com" },
    { name = "FABRICASSIST_S3_BUCKET", value = aws_s3_bucket.images.id },
    { name = "FABRICASSIST_S3_FORCE_PATH_STYLE", value = "false" },
    { name = "FABRICASSIST_RATE_LIMIT_ENABLED", value = "true" },
    { name = "FABRICASSIST_RATE_LIMIT_FAIL_OPEN", value = "false" },
    { name = "FABRICASSIST_METRICS_ENABLED", value = "true" },
    { name = "FABRICASSIST_VISION_DEBUG_LOGGING", value = "false" }
  ]
  secrets = [
    for name, value_from in var.application_secret_arns : {
      name      = name
      valueFrom = value_from
    }
  ]
}

data "aws_secretsmanager_secret_version" "database" {
  secret_id = var.database_credentials_secret_arn
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = local.name }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "public" {
  for_each                = local.public_subnets
  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = each.value
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-public-${each.key}" }
}

resource "aws_subnet" "private" {
  for_each          = local.private_subnets
  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = each.value
  tags              = { Name = "${local.name}-private-${each.key}" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = values(aws_subnet.public)[0].id
  depends_on    = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name   = "${local.name}-alb"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
}

resource "aws_security_group" "tasks" {
  name   = "${local.name}-tasks"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  #trivy:ignore:AVD-AWS-0104 Provider/catalog access requires audited HTTPS egress through the NAT gateway; application URL policy blocks private destinations.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "data" {
  name   = "${local.name}-data"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.tasks.id]
  }
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.tasks.id]
  }
}

resource "aws_kms_key" "images" {
  description             = "FabricAssist private image object encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "images" {
  name          = "alias/${local.name}-images"
  target_key_id = aws_kms_key.images.key_id
}

resource "aws_s3_bucket" "images" {
  bucket_prefix = "${local.name}-private-images-"
}

resource "aws_s3_bucket_public_access_block" "images" {
  bucket                  = aws_s3_bucket.images.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.images.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "images" {
  bucket = aws_s3_bucket.images.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  rule {
    id     = "expire-originals"
    status = "Enabled"
    filter { prefix = "private/" }
    expiration { days = var.image_retention_days }
    noncurrent_version_expiration { noncurrent_days = 7 }
  }
}

resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = values(aws_subnet.private)[*].id
}

resource "aws_db_instance" "postgres" {
  identifier                   = local.name
  engine                       = "postgres"
  engine_version               = "17"
  instance_class               = "db.t4g.medium"
  allocated_storage            = 50
  max_allocated_storage        = 200
  storage_encrypted            = true
  db_name                      = "fabricassist"
  username                     = jsondecode(data.aws_secretsmanager_secret_version.database.secret_string).username
  password                     = jsondecode(data.aws_secretsmanager_secret_version.database.secret_string).password
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [aws_security_group.data.id]
  publicly_accessible          = false
  multi_az                     = true
  backup_retention_period      = 14
  deletion_protection          = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${local.name}-final"
  auto_minor_version_upgrade   = true
  apply_immediately            = false
  performance_insights_enabled = true
}

resource "aws_elasticache_subnet_group" "this" {
  name       = local.name
  subnet_ids = values(aws_subnet.private)[*].id
}

resource "aws_elasticache_replication_group" "valkey" {
  replication_group_id       = local.name
  description                = "FabricAssist transient cache and Celery broker"
  engine                     = "valkey"
  engine_version             = "8.0"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.data.id]
}

resource "aws_ecr_repository" "api" {
  name                 = "fabricassist-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_repository" "worker" {
  name                 = "fabricassist-worker"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}/worker"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets" {
  name = "read-runtime-secrets"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = values(var.application_secret_arns)
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${local.name}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "images" {
  name = "private-image-access"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.images.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:ReEncryptFrom",
          "kms:ReEncryptTo",
        ]
        Resource = aws_kms_key.images.arn
      },
    ]
  })
}

#trivy:ignore:AVD-AWS-0053 The API ALB is the intentional public TLS ingress; API and worker tasks remain private.
resource "aws_lb" "api" {
  name                       = substr(local.name, 0, 32)
  load_balancer_type         = "application"
  internal                   = false
  drop_invalid_header_fields = true
  security_groups            = [aws_security_group.alb.id]
  subnets                    = values(aws_subnet.public)[*].id
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id
  health_check {
    path    = "/api/v1/health/ready"
    matcher = "200"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = "fabricassist-api"
    image        = var.api_image
    essential    = true
    environment  = concat(local.common_environment, [{ name = "FABRICASSIST_OTEL_SERVICE_NAME", value = "fabricassist-api" }])
    secrets      = local.secrets
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name        = "fabricassist-worker"
    image       = var.worker_image
    essential   = true
    command     = ["celery", "-A", "fabricassist.worker.celery_app:celery_app", "worker", "--loglevel=INFO"]
    environment = concat(local.common_environment, [{ name = "FABRICASSIST_OTEL_SERVICE_NAME", value = "fabricassist-worker" }])
    secrets     = local.secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "fabricassist-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = values(aws_subnet.private)[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "fabricassist-api"
    container_port   = 8000
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  depends_on = [aws_lb_listener.https]
}

resource "aws_ecs_service" "worker" {
  name            = "fabricassist-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = values(aws_subnet.private)[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
