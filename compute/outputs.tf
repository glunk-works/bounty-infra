output "instance_public_ip" {
  value       = aws_instance.testing_box.public_ip
  description = "The public IP address to connect to via SSH"
}