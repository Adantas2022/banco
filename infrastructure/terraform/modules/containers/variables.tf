variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for Container Apps environment"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID"
  type        = string
}

variable "acr_sku" {
  description = "ACR SKU"
  type        = string
  default     = "Basic"
}

variable "app_version" {
  description = "Application version/tag"
  type        = string
  default     = "latest"
}

variable "cosmosdb_connection_string" {
  description = "Cosmos DB connection string"
  type        = string
  sensitive   = true
}

variable "redis_connection_string" {
  description = "Redis connection string"
  type        = string
  sensitive   = true
}

variable "storage_connection_string" {
  description = "Storage account connection string"
  type        = string
  sensitive   = true
}

variable "storage_container_name" {
  description = "Storage container name"
  type        = string
}

variable "api_cpu" {
  description = "CPU cores for API"
  type        = number
  default     = 0.5
}

variable "api_memory" {
  description = "Memory for API"
  type        = string
  default     = "1Gi"
}

variable "api_min_replicas" {
  description = "Minimum replicas for API"
  type        = number
  default     = 1
}

variable "api_max_replicas" {
  description = "Maximum replicas for API"
  type        = number
  default     = 5
}

variable "worker_cpu" {
  description = "CPU cores for workers"
  type        = number
  default     = 1.0
}

variable "worker_memory" {
  description = "Memory for workers"
  type        = string
  default     = "2Gi"
}

variable "worker_digital_min_replicas" {
  description = "Minimum replicas for digital worker"
  type        = number
  default     = 1
}

variable "worker_digital_max_replicas" {
  description = "Maximum replicas for digital worker"
  type        = number
  default     = 3
}

variable "worker_ocr_min_replicas" {
  description = "Minimum replicas for OCR worker"
  type        = number
  default     = 1
}

variable "worker_ocr_max_replicas" {
  description = "Maximum replicas for OCR worker"
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
