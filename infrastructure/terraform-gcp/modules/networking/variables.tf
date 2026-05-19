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

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "subnet_ranges" {
  description = "Subnet IP ranges"
  type = object({
    cloudrun       = string
    serverless_vpc = string
    redis          = string
  })
}

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}
