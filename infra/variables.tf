variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "ai-trends-explorer"
}

variable "instance_type" {
  description = "EC2 instance type (t3.small minimum for sentence-transformers)"
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 access"
  type        = string
}

variable "ssh_cidr" {
  description = "CIDR block allowed for SSH access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "repo_url" {
  description = "Git repository URL to clone"
  type        = string
  default     = "https://github.com/your-org/PDAI-Project.git"
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
  default     = "changeme"
}

# --- API Keys (all sensitive) ---

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Groq API key for Llama critic"
  type        = string
  sensitive   = true
}

variable "google_ai_api_key" {
  description = "Google AI API key for Gemini fallback"
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_token" {
  description = "GitHub token for trending source"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langchain_api_key" {
  description = "LangSmith API key for tracing"
  type        = string
  sensitive   = true
  default     = ""
}
