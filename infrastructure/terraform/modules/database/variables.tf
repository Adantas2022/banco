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

variable "subnet_id" {
  description = "Subnet ID for private endpoint"
  type        = string
}

variable "private_dns_zone_id" {
  description = "Private DNS zone ID"
  type        = string
}

variable "throughput" {
  description = "Cosmos DB throughput (RU/s)"
  type        = number
  default     = 400
}

variable "max_throughput" {
  description = "Cosmos DB max autoscale throughput (RU/s)"
  type        = number
  default     = 4000
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
