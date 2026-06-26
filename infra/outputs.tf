output "ecr_repository_url" {
  value       = aws_ecr_repository.scanner_repo.repository_url
  description = "The URL of the ECR repository"
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.scanner_cluster.name
  description = "The name of the ECS cluster"
}

output "subnet_id" {
  value       = aws_subnet.public_subnet.id
  description = "The ID of the public subnet for the Fargate task"
}

output "security_group_id" {
  value       = aws_security_group.fargate_sg.id
  description = "The ID of the zero-ingress security group"
}