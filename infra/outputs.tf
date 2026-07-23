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

output "vultr_firewall_group_id" {
  value       = vultr_firewall_group.scan_vm.id
  description = "Vultr firewall group ID (no ingress rules) for per-scan VM attachment"
}

output "reserved_ip_id" {
  value       = one(vultr_reserved_ip.scan_vm[*].id)
  description = "Reserved IP resource ID, for the create API's reserved_ipv4 field. Null when reserved_ip_enabled is false."
}

output "reserved_ip_address" {
  value       = one(vultr_reserved_ip.scan_vm[*].subnet)
  description = "The reserved IP's actual address, for program registration. Null when reserved_ip_enabled is false."
}

output "vultr_region" {
  value       = var.vultr_region
  description = "Vultr region used for the reserved IP and (by run-scan.yml) per-scan VMs -- single source of truth, not duplicated as a workflow literal"
}

output "vultr_plan" {
  value       = var.vultr_plan
  description = "Vultr instance plan used by run-scan.yml for per-scan VMs"
}