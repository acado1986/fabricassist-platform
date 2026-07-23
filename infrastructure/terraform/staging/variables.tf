variable "aws_region" {
  description = "AWS region selected by the deployment environment."
  type        = string
}

variable "environment" {
  description = "Non-production environment name."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["development", "staging"], var.environment)
    error_message = "This root module is intentionally restricted to development/staging."
  }
}

variable "availability_zones" {
  description = "Exactly two availability zones in aws_region."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Provide exactly two availability zones."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "api_image" {
  description = "Immutable API image reference, preferably an ECR digest."
  type        = string
}

variable "worker_image" {
  description = "Immutable worker image reference, preferably an ECR digest."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate for the API listener."
  type        = string
}

variable "api_hostname" {
  description = "Public HTTPS hostname used for API/CORS configuration."
  type        = string
}

variable "app_hostname" {
  description = "Public HTTPS hostname of the Expo web application."
  type        = string
}

variable "database_credentials_secret_arn" {
  description = "Secrets Manager JSON secret containing username and password for RDS."
  type        = string
  sensitive   = true
}

variable "application_secret_arns" {
  description = "Map of FABRICASSIST_* environment name to Secrets Manager secret ARN."
  type        = map(string)
  sensitive   = true
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "image_retention_days" {
  type    = number
  default = 30
}
