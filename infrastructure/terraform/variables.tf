variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "irpf-processor"
}

variable "environment" {
  description = "Environment name"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "brazilsouth"
}

variable "vnet_address_space" {
  description = "Address space for VNet"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_prefixes" {
  description = "Subnet address prefixes"
  type = object({
    container_apps = string
    database       = string
    cache          = string
    private_endpoints = string
  })
  default = {
    container_apps    = "10.0.1.0/24"
    database          = "10.0.2.0/24"
    cache             = "10.0.3.0/24"
    private_endpoints = "10.0.4.0/24"
  }
}

variable "cosmosdb_throughput" {
  description = "Cosmos DB throughput (RU/s)"
  type        = number
  default     = 400
}

variable "cosmosdb_max_throughput" {
  description = "Cosmos DB max autoscale throughput (RU/s)"
  type        = number
  default     = 4000
}

variable "redis_sku" {
  description = "Redis SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Basic"
}

variable "redis_family" {
  description = "Redis family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Redis cache capacity"
  type        = number
  default     = 0
}

variable "api_cpu" {
  description = "CPU cores for API container"
  type        = number
  default     = 0.5
}

variable "api_memory" {
  description = "Memory for API container in Gi"
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
  description = "CPU cores for worker container"
  type        = number
  default     = 1.0
}

variable "worker_memory" {
  description = "Memory for worker container in Gi"
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

variable "acr_sku" {
  description = "Azure Container Registry SKU"
  type        = string
  default     = "Basic"
}

variable "app_version" {
  description = "Application version/tag to deploy"
  type        = string
  default     = "latest"
}

variable "enable_monitoring" {
  description = "Enable Azure Monitor and alerts"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Log Analytics workspace retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
