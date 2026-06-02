terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # PARTIAL BACKEND: The 'bucket' is deliberately omitted here.
  # It will be injected dynamically via GitHub Actions / Infisical.
  backend "s3" {
    key            = "compute/tofu.tfstate"
    region         = "us-east-1"
    dynamodb_table = "vms-tofu-lock-table"
    encrypt        = true
  }
}
provider "aws" {
  region = var.aws_region
}

# Network Setup
resource "aws_vpc" "sec_vpc" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name = "vms-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.sec_vpc.id
  tags = {
    Name = "vms-igw"
  }
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.sec_vpc.id
  cidr_block              = "10.10.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = {
    Name = "vms-public-subnet"
  }
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

# Strict Security Group - Whitelists your management IP
resource "aws_security_group" "testing_sg" {
  name        = "vms-testing-sg"
  description = "Allow inbound SSH access from trusted operator IP"
  vpc_id      = aws_vpc.sec_vpc.id

  ingress {
    description = "Operator SSH Access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.operator_ip]
  }

  egress {
    description = "Unrestricted Outbound for Scanning"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vms-security-group"
  }
}

# IAM Role allowing instance to write data directly to your findings bucket
resource "aws_iam_role" "instance_role" {
  name = "vms-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_write_policy" {
  name        = "vms-s3-write-policy"
  description = "Allows access to findings bucket and KMS decryption"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.findings_bucket_name}",
          "arn:aws:s3:::${var.findings_bucket_name}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "role_attach" {
  role       = aws_iam_role.instance_role.name
  policy_arn = aws_iam_policy.s3_write_policy.arn
}

resource "aws_iam_instance_profile" "instance_profile" {
  name = "vms-instance-profile"
  role = aws_iam_role.instance_role.name
}

# Fetch Latest Stable Ubuntu 24.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# SSH Key Pair
resource "aws_key_pair" "deployer" {
  key_name   = "vms-operator-key"
  public_key = var.public_key
}

# Testing Instance
resource "aws_instance" "testing_box" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.testing_sg.id]
  key_name               = aws_key_pair.deployer.key_name
  iam_instance_profile   = aws_iam_instance_profile.instance_profile.name

  root_block_device {
    volume_size           = var.volume_size
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = file("${path.module}/scripts/user_data.sh")

  tags = {
    Name      = "vms-testing-machine"
    ManagedBy = "OpenTofu"
  }
}