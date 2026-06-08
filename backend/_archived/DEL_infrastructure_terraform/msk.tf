# Route Engine Evolution - AWS MSK Kafka Cluster
# Terraform configuration for Kafka infrastructure
# Owner: DAEDALUS (Infrastructure Lead)

terraform {
  required_version = ">= 1.0.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "routemaster-terraform-state"
    key    = "kafka/msk/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "RouteEngine"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Variables
variable "aws_region" {
  default = "ap-south-1"
}

variable "environment" {
  default = "staging"
}

variable "cluster_name" {
  default = "route-engine-kafka"
}

variable "kafka_version" {
  default = "2.8.1"
}

# Local values
locals {
  tags = {
    Project     = "RouteEngine"
    Environment = var.environment
    Owner       = "DAEDALUS"
  }
}

# Security Group for MSK
resource "aws_security_group" "msk" {
  name        = "${var.cluster_name}-sg"
  description = "Security group for MSK cluster"
  vpc_id      = module.vpc.vpc_id
  
  # Allow inbound from application tier
  ingress {
    from_port   = 9092
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [module.vpc.private_subnets_cidr_blocks[0]]
    description = "Kafka client access"
  }
  
  # Allow inbound from other brokers
  ingress {
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
    description = "Inter-broker communication"
  }
  
  # Allow Zookeeper access
  ingress {
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
    description = "Zookeeper access"
  }
  
  # Outbound rules
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = local.tags
}

# MSK Configuration
resource "aws_msk_configuration" "msk" {
  name = "${var.cluster_name}-config"
  
  kafka_versions = [var.kafka_version]
  
  server_properties = <<-PROPERTIES
    auto.create.topics.enable = true
    default.replication.factor = 3
    delete.topic.enable = true
    log.retention.hours = 168
    min.insync.replicas = 2
    num.io.threads = 8
    num.network.threads = 5
    num.partitions = 6
    num.replica.fetchers = 2
    socket.request.max.bytes = 104857600
    zookeeper.connection.timeout.ms = 6000
    zookeeper.session.timeout.ms = 30000
  PROPERTIES
}

# MSK Cluster
resource "aws_msk_cluster" "msk" {
  cluster_name           = var.cluster_name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.environment == "production" ? 6 : 3
  
  broker_node_group_info {
    instance_type   = var.environment == "production" ? "kafka.m5.2xlarge" : "kafka.m5.large"
    client_subnets  = module.vpc.private_subnets
    storage_info {
      volume_size = var.environment == "production" ? 2000 : 1000
      volume_type = "gp3"
    }
    security_groups = [aws_security_group.msk.id]
  }
  
  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
  
  configuration_info {
    arn      = aws_msk_configuration.msk.arn
    revision = aws_msk_configuration.msk.latest_revision
  }
  
  client_authentication {
    sasl {
      scram = true
    }
  }
  
  logging_info {
    broker_logs {
      cloudwatch_logs {
        log_group = aws_cloudwatch_log_group.msk.name
      }
      s3 {
        bucket = aws_s3_bucket.kafka_logs.id
        prefix = "logs/"
      }
    }
  }
  
  timeouts {
    create = "60m"
    update = "60m"
    delete = "60m"
  }
  
  tags = local.tags
}

# KMS Key for encryption
resource "aws_kms_key" "msk" {
  description             = "KMS key for MSK encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM policies"
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action = "kms:*"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "Allow MSK access"
        Effect = "Allow"
        Principal = {
          Service = "kafka.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.cluster_name}"
  retention_in_days = 14
  
  tags = local.tags
}

# S3 Bucket for logs
resource "aws_s3_bucket" ".kafka_logs" {
  bucket = "routemaster-${var.environment}-kafka-logs"
  
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

resource "aws_s3_bucket_public_access_block" "kafka_logs" {
  bucket = aws_s3_bucket.kafka_logs.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Secrets Manager Secret for SASL credentials
resource "aws_secretsmanager_secret" "kafka_credentials" {
  name = "routemaster/${var.environment}/kafka/credentials"
  
  description = "SASL credentials for Kafka access"
  
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "kafka_credentials" {
  secret_id = aws_secretsmanager_secret.kafka_credentials.id
  
  secret_string = jsonencode({
    username = "route-engine"
    password = random_password.kafka_password.result
  })
}

# Random password for Kafka
resource "random_password" "kafka_password" {
  length  = 32
  special = false
}

# Data sources
data "aws_caller_identity" "current" {}

data "aws_vpc" "default" {
  default = true
}

# VPC Module (simplified - in production use terraform-aws-modules/vpc)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  
  name = "routemaster-${var.environment}"
  cidr = var.environment == "production" ? "10.0.0.0/16" : "10.1.0.0/16"
  
  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = var.environment == "production" ? ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"] : ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
  public_subnets  = var.environment == "production" ? ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"] : ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]
  
  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  enable_dns_hostnames   = true
  enable_dns_support     = true
  
  tags = local.tags
}

# Outputs
output "bootstrap_brokers" {
  description = "MSK cluster bootstrap brokers"
  value       = aws_msk_cluster.msk.bootstrap_brokers
  sensitive   = true
}

output "bootstrap_brokers_tls" {
  description = "MSK cluster bootstrap brokers (TLS)"
  value       = aws_msk_cluster.msk.bootstrap_brokers_tls
  sensitive   = true
}

output "zookeeper_connect_string" {
  description = "Zookeeper connection string"
  value       = aws_msk_cluster.msk.zookeeper_connect_string
  sensitive   = true
}

output "arn" {
  description = "MSK cluster ARN"
  value       = aws_msk_cluster.msk.arn
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.msk.id
}

output "secrets_manager_arn" {
  description = "Secrets Manager ARN for Kafka credentials"
  value       = aws_secretsmanager_secret.kafka_credentials.arn
}

# Cost estimation output
output "estimated_monthly_cost" {
  description = "Estimated monthly cost in USD"
  value       = var.environment == "production" ? 450 : 150
}