variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
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

variable "vpc_connector_id" {
  description = "VPC Access Connector ID"
  type        = string
}

variable "app_version" {
  description = "Application version/tag"
  type        = string
  default     = "latest"
}

variable "mongodb_connection_string" {
  description = "MongoDB connection string"
  type        = string
  sensitive   = true
}

variable "redis_host" {
  description = "Redis host"
  type        = string
}

variable "redis_port" {
  description = "Redis port"
  type        = number
}

variable "storage_bucket" {
  description = "Cloud Storage bucket name"
  type        = string
}

variable "api_cpu" {
  description = "CPU for API"
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Memory for API"
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
  description = "CPU for workers"
  type        = string
  default     = "2"
}

variable "worker_memory" {
  description = "Memory for workers"
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

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}
