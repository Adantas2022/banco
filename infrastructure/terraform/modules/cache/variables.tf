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

variable "sku" {
  description = "Redis SKU"
  type        = string
  default     = "Basic"
}

variable "family" {
  description = "Redis family"
  type        = string
  default     = "C"
}

variable "capacity" {
  description = "Redis capacity"
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
