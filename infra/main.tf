terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.52"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ==========================================
# 1. NETWORK (Zero-Trust Ingress)
# ==========================================
resource "aws_vpc" "sec_vpc" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "bounty-fargate-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.sec_vpc.id
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.sec_vpc.id
  cidr_block              = "10.10.1.0/24"
  map_public_ip_on_launch = true # Required for Fargate to pull ECR images w/o NAT Gateway
  availability_zone       = "${var.aws_region}a"
}

resource "aws_route_table" "rt" {
  vpc_id = aws_vpc.sec_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "rta" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.rt.id
}

# Strict Security Group - NO INBOUND TRAFFIC ALLOWED
resource "aws_security_group" "fargate_sg" {
  name        = "bounty-fargate-sg"
  description = "No ingress, unrestricted egress for scanning"
  vpc_id      = aws_vpc.sec_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ==========================================
# 2. CONTAINER REGISTRY & CLUSTER
# ==========================================
resource "aws_ecr_repository" "scanner_repo" {
  name                 = "glunk-works/bounty-scanner"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecs_cluster" "scanner_cluster" {
  name = "bounty-scanner-cluster"
}

resource "aws_cloudwatch_log_group" "scanner_logs" {
  name              = "/ecs/bounty-scanner"
  retention_in_days = 14
}

# ==========================================
# 3. IAM & TASK DEFINITION
# ==========================================
# Task Execution Role: Allows AWS to pull the image from ECR and write logs
resource "aws_iam_role" "execution_role" {
  name = "bounty-fargate-execution-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy_attachment" "exec_attach" {
  role       = aws_iam_role.execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task Role: Allows the Python script INSIDE the container to write to S3
resource "aws_iam_role" "task_role" {
  name = "bounty-fargate-task-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}
resource "aws_iam_policy" "s3_write_policy" {
  name = "bounty-s3-write-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3Access"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.findings_bucket_name}",
          "arn:aws:s3:::${var.findings_bucket_name}/*"
        ]
      },
      {
        Sid    = "AllowKMSEncryption"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "task_s3_attach" {
  role       = aws_iam_role.task_role.name
  policy_arn = aws_iam_policy.s3_write_policy.arn
}

resource "aws_ecs_task_definition" "scanner_task" {
  family                   = "bounty-scanner-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024 # 1 vCPU
  memory                   = 2048 # 2 GB RAM
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name      = "scanner-container"
      image     = "${aws_ecr_repository.scanner_repo.repository_url}:${var.image_tag}"
      essential = true
      environment = [
        { name = "S3_BUCKET_NAME", value = var.findings_bucket_name }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.scanner_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  # T3(d): after the bootstrap apply, `build-image.yml` registers new revisions
  # of this task definition directly against ECS — one per merge to main, image
  # tagged by commit sha, never `:latest` — so every deploy is CI-gated
  # (branch protection requires `lint`/`test` green before merge) and every
  # running image is traceable to the commit that produced it. `ignore_changes`
  # stops Tofu from reverting that on the next unrelated apply: this field is
  # deliberately not fought over between CI and IaC. BI-D2's plan+approval gate
  # still covers everything else in this resource and this file — it governs
  # AWS topology changes, not routine application image delivery.
  lifecycle {
    ignore_changes = [container_definitions]
  }
}