variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "irpf-processor"
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "southamerica-east1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_ranges" {
  description = "Subnet IP ranges"
  type = object({
    cloudrun       = string
    serverless_vpc = string
    redis          = string
  })
  default = {
    cloudrun       = "10.0.1.0/24"
    serverless_vpc = "10.0.2.0/28"
    redis          = "10.0.3.0/24"
  }
}

variable "mongodb_atlas_public_key" {
  description = "MongoDB Atlas public key"
  type        = string
  sensitive   = true
}

variable "mongodb_atlas_private_key" {
  description = "MongoDB Atlas private key"
  type        = string
  sensitive   = true
}

variable "mongodb_atlas_org_id" {
  description = "MongoDB Atlas organization ID"
  type        = string
}

variable "mongodb_cluster_tier" {
  description = "MongoDB Atlas cluster tier"
  type        = string
  default     = "M10"
}

variable "redis_tier" {
  description = "Memorystore Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
}

variable "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "api_cpu" {
  description = "CPU for API container"
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Memory for API container"
  type        = string
  default     = "512Mi"
}

variable "api_min_instances" {
  description = "Minimum instances for API"
  type        = number
  default     = 1
}

variable "api_max_instances" {
  description = "Maximum instances for API"
  type        = number
  default     = 5
}

variable "worker_cpu" {
  description = "CPU for worker container"
  type        = string
  default     = "2"
}

variable "worker_memory" {
  description = "Memory for worker container"
  type        = string
  default     = "2Gi"
}

variable "worker_digital_min_instances" {
  description = "Minimum instances for digital worker"
  type        = number
  default     = 1
}

variable "worker_digital_max_instances" {
  description = "Maximum instances for digital worker"
  type        = number
  default     = 3
}

variable "worker_ocr_min_instances" {
  description = "Minimum instances for OCR worker"
  type        = number
  default     = 1
}

variable "worker_ocr_max_instances" {
  description = "Maximum instances for OCR worker"
  type        = number
  default     = 2
}

variable "app_version" {
  description = "Application version/tag to deploy"
  type        = string
  default     = "latest"
}

variable "enable_monitoring" {
  description = "Enable Cloud Monitoring alerts"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}
