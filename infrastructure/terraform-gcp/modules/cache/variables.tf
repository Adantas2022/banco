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

variable "vpc_network_id" {
  description = "VPC network ID"
  type        = string
}

variable "tier" {
  description = "Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
}

variable "memory_size_gb" {
  description = "Memory size in GB"
  type        = number
  default     = 1
}

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}
