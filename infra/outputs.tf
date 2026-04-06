output "instance_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.app.public_ip
}

output "api_url" {
  description = "API endpoint URL"
  value       = "http://${aws_instance.app.public_ip}:8000"
}

output "dashboard_url" {
  description = "Dashboard URL (served by nginx)"
  value       = "http://${aws_instance.app.public_ip}"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ec2-user@${aws_instance.app.public_ip}"
}
